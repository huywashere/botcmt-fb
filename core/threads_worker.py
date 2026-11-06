import time
import random
import threading
from datetime import datetime
from core.db import (
    get_setting, set_setting, log_threads_comment,
    is_threads_post_already_commented, get_recent_threads_logs
)
from core.ai_engine import AIEngine
from core.threads_engine import ThreadsEngine
from core.telegram_notifier import TelegramNotifier

class ThreadsWorker:
    def __init__(self, ui_callback=None):
        self.is_running = False
        self.worker_thread = None
        self.ui_callback = ui_callback
        self.engine = None
        self.last_scanned_posts = []

    def notify_ui(self, event_type, data):
        """Gửi thông báo cập nhật về giao diện"""
        if self.ui_callback:
            try:
                self.ui_callback(event_type, data)
            except Exception as e:
                print("Lỗi callback UI Threads:", str(e))

    def check_active_time(self):
        """Kiểm tra xem thời điểm hiện tại có nằm trong khung giờ cho phép không"""
        start_str = get_setting("active_start", "08:00")
        end_str = get_setting("active_end", "23:00")
        try:
            now_time = datetime.now().time()
            start_time = datetime.strptime(start_str, "%H:%M").time()
            end_time = datetime.strptime(end_str, "%H:%M").time()
            return start_time <= now_time <= end_time
        except Exception:
            return True

    def count_today_comments(self):
        """Đếm số bình luận Threads đã gửi thành công trong ngày hôm nay"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        logs = get_recent_threads_logs(limit=200)
        return sum(1 for l in logs if l.get("status") == "Đã gửi" and str(l.get("created_at", "")).startswith(today_str))

    def scan_only(self):
        """Chức năng 'Quét thử Threads - chưa gửi' để xem trước danh sách bài cào được và cmt dự kiến"""
        def _job():
            self.notify_ui("threads_status", "Đang quét thảo luận phim trên Threads...")
            engine = ThreadsEngine(headless=True)
            try:
                posts = engine.scan_movie_threads(max_posts=5)
                self.last_scanned_posts = []
                for p in posts:
                    predicted_comment = AIEngine.generate_comment(
                        p["content"],
                        fanpage_name="Flex Phim",
                        platform="Threads",
                        is_general_post=p.get("is_general_post", False)
                    )
                    item = {
                        "post_url": p["url"],
                        "post_snippet": p["content"],
                        "comment_content": predicted_comment,
                        "status": "Chưa gửi (Quét thử)",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    self.last_scanned_posts.append(item)
                    self.notify_ui("threads_new_post_scanned", item)
                self.notify_ui("threads_status", f"Quét Threads hoàn tất. Tìm thấy {len(self.last_scanned_posts)} bài thảo luận phim.")
            except Exception as e:
                self.notify_ui("threads_status", f"Lỗi quét Threads: {str(e)}")
            finally:
                engine.close()

        threading.Thread(target=_job, daemon=True).start()

    def start_auto(self):
        """Bắt đầu chu trình tự động cào bài và bình luận thông minh trên Threads"""
        if self.is_running:
            return

        self.is_running = True
        set_setting("threads_auto_comment_enabled", "1")
        self.notify_ui("threads_auto_state_changed", True)

        def _loop():
            try:
                # Kiểm tra cookie trước để không bị treo
                if not ThreadsEngine.check_cookie_login():
                    self.notify_ui("threads_status", "Bot Threads đang kiểm tra phiên đăng nhập...")
                    self.engine = ThreadsEngine(headless=True)
                    is_logged = self.engine.check_is_logged_in()
                    if not is_logged:
                        msg = "Chưa đăng nhập Threads! Hãy bấm 'Đăng nhập Threads' trước."
                        self.notify_ui("threads_status", msg)
                        self.stop()
                        return
                else:
                    self.engine = ThreadsEngine(headless=True)

                self.notify_ui("threads_status", "Tài khoản Threads đã sẵn sàng! Bắt đầu cào chủ đề phim...")
                session_start_time = time.time()
                consecutive_errors = 0

                while self.is_running:
                    # 1. Hẹn giờ phiên chạy
                    duration_mins = int(get_setting("session_duration_minutes", "0"))
                    if duration_mins > 0:
                        elapsed_mins = (time.time() - session_start_time) / 60
                        if elapsed_mins >= duration_mins:
                            msg = f"Đã hết thời hạn phiên ({duration_mins} phút). Bot Threads tạm dừng an toàn!"
                            self.notify_ui("threads_status", msg)
                            break

                    # 2. Giới hạn bình luận trong ngày
                    daily_limit = int(get_setting("threads_daily_limit", "30"))
                    today_count = self.count_today_comments()
                    if today_count >= daily_limit:
                        msg = f"Đã đạt giới hạn {today_count}/{daily_limit} cmt Threads hôm nay. Tự ngắt an toàn!"
                        self.notify_ui("threads_status", msg)
                        if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("threads_telegram_alerts_enabled", "1") == "1":
                            TelegramNotifier.send_message(f"🧵 <b>[Threads Bot Cảnh Báo]</b> {msg}")
                        break

                    # 3. Khung giờ an toàn
                    if not self.check_active_time():
                        self.notify_ui("threads_status", "Ngoài khung giờ hoạt động. Tạm nghỉ bảo vệ tài khoản...")
                        for _ in range(300):
                            if not self.is_running:
                                break
                            time.sleep(1)
                        continue

                    # 4. Cào bài thảo luận phim ảnh
                    self.notify_ui("threads_status", "Đang cào các chủ đề thảo luận phim mới trên Threads...")
                    posts = self.engine.scan_movie_threads(max_posts=6)
                    commented_this_round = 0

                    for p in posts:
                        if not self.is_running:
                            break

                        post_url = p["url"]
                        post_content = p["content"]

                        if is_threads_post_already_commented(post_url):
                            continue

                        is_general = p.get("is_general_post", False)

                        # Sinh bình luận thông minh bằng Gemini (nhắc tự nhiên: ghé flexphim, trên flexphim...)
                        if is_general:
                            self.notify_ui("threads_status", f"AI đang tạo bình luận cho bài Threads thường: {post_url[:35]}...")
                        else:
                            self.notify_ui("threads_status", f"AI đang phân tích bài phim Threads: {post_url[:35]}...")

                        comment_text = AIEngine.generate_comment(
                            post_content, 
                            fanpage_name="Flexphim",
                            platform="Threads",
                            is_general_post=is_general
                        )

                        # Thực hiện bình luận trên Threads
                        self.notify_ui("threads_status", f"Đang gửi bình luận vào Threads: {post_url[:35]}...")
                        success, msg = self.engine.comment_on_thread(post_url, comment_text)

                        if success:
                            consecutive_errors = 0
                            commented_this_round += 1
                            log_threads_comment(post_url, post_content, comment_text, status="Đã gửi")
                            self.notify_ui("threads_status", f"Đã gửi cmt thành công lên bài Threads: {post_url[:35]}...")

                            # Bắn thông báo Telegram
                            if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("threads_telegram_alerts_enabled", "1") == "1":
                                today_count = self.count_today_comments()
                                daily_limit = int(get_setting("threads_daily_limit", "30"))
                                TelegramNotifier.notify_threads_comment(
                                    post_url=post_url,
                                    post_content=post_content,
                                    comment_text=comment_text,
                                    author=p.get("author", ""),
                                    is_general=is_general,
                                    is_manual=False,
                                    today_count=today_count,
                                    daily_limit=daily_limit
                                )

                            # Giãn cách an toàn (~2 phút / bài)
                            min_delay = int(get_setting("threads_min_delay", "110"))
                            max_delay = int(get_setting("threads_max_delay", "130"))
                            chosen_delay = random.randint(min_delay, max_delay)

                            for remaining in range(chosen_delay, 0, -1):
                                if not self.is_running:
                                    break
                                mins = remaining // 60
                                secs = remaining % 60
                                self.notify_ui("threads_countdown", f"chờ bài Threads tiếp theo: {mins}:{secs:02d}")
                                time.sleep(1)
                            self.notify_ui("threads_countdown", "")

                        else:
                            consecutive_errors += 1
                            log_threads_comment(post_url, post_content, comment_text, status="Lỗi", error=msg)
                            self.notify_ui("threads_status", f"Lỗi cmt Threads: {msg}")

                            if consecutive_errors >= 4:
                                self.notify_ui("threads_status", "Phát hiện 4 lỗi liên tiếp. Dừng bot Threads để bảo vệ tài khoản.")
                                if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("threads_telegram_alerts_enabled", "1") == "1":
                                    TelegramNotifier.send_message(f"⚠️ <b>[Threads Bot Cảnh Báo]</b> 4 lỗi liên tiếp ({msg}). Đã tự dừng!")
                                self.stop()
                                return

                            time.sleep(15)

                    if commented_this_round == 0 and self.is_running:
                        scan_interval = int(get_setting("threads_scan_interval", "2"))
                        self.notify_ui("threads_status", f"Lượt cào vừa rồi đã xong hoặc chưa có bài mới. Lần cào tiếp sau {scan_interval} phút...")
                        wait_seconds = max(15, scan_interval * 60)
                        for remaining in range(wait_seconds, 0, -1):
                            if not self.is_running:
                                break
                            mins = remaining // 60
                            secs = remaining % 60
                            self.notify_ui("threads_countdown", f"cào đợt tiếp: {mins}:{secs:02d}")
                            time.sleep(1)
                        self.notify_ui("threads_countdown", "")

            except Exception as e:
                err_text = str(e)
                print("Lỗi tiến trình Threads Worker:", err_text)
                self.notify_ui("threads_status", f"Lỗi Threads: {err_text}")
            finally:
                if self.engine:
                    try:
                        self.engine.close()
                    except Exception:
                        pass
                    self.engine = None
                self.is_running = False
                self.notify_ui("threads_auto_state_changed", False)
                self.notify_ui("threads_countdown", "")
                self.notify_ui("threads_status", "Hệ thống Threads Auto Bot đã dừng.")

        self.worker_thread = threading.Thread(target=_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Dừng tiến trình Threads"""
        self.is_running = False
        self.notify_ui("threads_auto_state_changed", False)
        self.notify_ui("threads_countdown", "")
        self.notify_ui("threads_status", "Đang dừng Threads Auto Bot...")
        if self.engine:
            try:
                self.engine.close()
            except Exception:
                pass
            self.engine = None
