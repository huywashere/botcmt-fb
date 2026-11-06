import time
import random
import threading
from datetime import datetime
from core.db import (
    get_setting, set_setting, log_x_comment,
    is_x_post_already_commented, get_recent_x_logs
)
from core.ai_engine import AIEngine, is_movie_related
from core.x_engine import XEngine
from core.telegram_notifier import TelegramNotifier

class XWorker:
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
                print("Lỗi callback UI X (Twitter):", str(e))

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
        """Đếm số bình luận X đã gửi thành công trong ngày hôm nay"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        logs = get_recent_x_logs(limit=200)
        return sum(1 for l in logs if l.get("status") == "Đã gửi" and str(l.get("created_at", "")).startswith(today_str))

    def scan_only(self):
        """Chức năng 'Quét thử 𝕏 - chưa gửi' để xem trước danh sách tweet cào được và cmt dự kiến"""
        def _job():
            self.notify_ui("x_status", "Đang quét thảo luận phim trên 𝕏 (Twitter)...")
            engine = XEngine(headless=True)
            try:
                posts = engine.scan_movie_tweets(max_posts=5)
                self.last_scanned_posts = []
                for p in posts:
                    predicted_comment = AIEngine.generate_comment(
                        p["content"],
                        fanpage_name="Flex Phim",
                        platform="𝕏 (Twitter)",
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
                    self.notify_ui("x_new_post_scanned", item)
                self.notify_ui("x_status", f"Quét 𝕏 hoàn tất. Tìm thấy {len(self.last_scanned_posts)} tweet thảo luận phim.")
            except Exception as e:
                self.notify_ui("x_status", f"Lỗi quét 𝕏: {str(e)}")
            finally:
                engine.close()

        threading.Thread(target=_job, daemon=True).start()

    def start_auto(self):
        """Bắt đầu chu trình tự động cào tweet và bình luận thông minh trên 𝕏 (Twitter)"""
        if self.is_running:
            return

        self.is_running = True
        set_setting("x_auto_comment_enabled", "1")
        self.notify_ui("x_auto_state_changed", True)

        def _loop():
            try:
                # Kiểm tra cookie trước để không bị treo
                if not XEngine.check_cookie_login():
                    self.notify_ui("x_status", "Bot 𝕏 đang kiểm tra phiên đăng nhập...")
                    self.engine = XEngine(headless=True)
                    is_logged = self.engine.check_is_logged_in()
                    if not is_logged:
                        msg = "Chưa đăng nhập 𝕏! Hãy bấm 'Đăng nhập 𝕏' trước."
                        self.notify_ui("x_status", msg)
                        self.stop()
                        return
                else:
                    self.engine = XEngine(headless=True)

                self.notify_ui("x_status", "Tài khoản 𝕏 đã sẵn sàng! Bắt đầu cào chủ đề phim...")
                session_start_time = time.time()
                consecutive_errors = 0

                while self.is_running:
                    # 1. Hẹn giờ phiên chạy
                    duration_mins = int(get_setting("session_duration_minutes", "0"))
                    if duration_mins > 0:
                        elapsed_mins = (time.time() - session_start_time) / 60
                        if elapsed_mins >= duration_mins:
                            msg = f"Đã hết thời hạn phiên ({duration_mins} phút). Bot 𝕏 tạm dừng an toàn!"
                            self.notify_ui("x_status", msg)
                            break

                    # 2. Giới hạn bình luận trong ngày
                    daily_limit = int(get_setting("x_daily_limit", "100"))
                    today_count = self.count_today_comments()
                    if today_count >= daily_limit:
                        msg = f"Đã đạt giới hạn {today_count}/{daily_limit} cmt 𝕏 hôm nay. Tự ngắt an toàn!"
                        self.notify_ui("x_status", msg)
                        if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("x_telegram_alerts_enabled", "1") == "1":
                            TelegramNotifier.send_message(f"𝕏 <b>[𝕏 Bot Cảnh Báo]</b> {msg}")
                        break

                    # 3. Khung giờ an toàn
                    if not self.check_active_time():
                        self.notify_ui("x_status", "Ngoài khung giờ hoạt động. Tạm nghỉ bảo vệ tài khoản...")
                        for _ in range(300):
                            if not self.is_running:
                                break
                            time.sleep(1)
                        continue

                    # 4. Cào bài thảo luận phim ảnh trên X
                    self.notify_ui("x_status", "Đang cào các chủ đề thảo luận phim mới trên 𝕏...")
                    posts = self.engine.scan_movie_tweets(max_posts=6)
                    commented_this_round = 0

                    for p in posts:
                        if not self.is_running:
                            break

                        post_url = p["url"]
                        post_content = p["content"]

                        if is_x_post_already_commented(post_url):
                            continue

                        # Đảm bảo bài viết bắt buộc phải liên quan đến phim ảnh (dù nhẹ)
                        if not is_movie_related(post_content):
                            continue

                        is_general = p.get("is_general_post", False)

                        # Sinh bình luận thông minh bằng Gemini (nhắc tự nhiên: ghé flexphim, trên flexphim...)
                        if is_general:
                            self.notify_ui("x_status", f"AI đang tạo bình luận cho Tweet thường: {post_url[:35]}...")
                        else:
                            self.notify_ui("x_status", f"AI đang phân tích Tweet phim: {post_url[:35]}...")

                        comment_text = AIEngine.generate_comment(
                            post_content, 
                            fanpage_name="Flexphim",
                            platform="𝕏 (Twitter)",
                            is_general_post=is_general
                        )

                        # Thực hiện bình luận trên X
                        self.notify_ui("x_status", f"Đang gửi bình luận vào 𝕏: {post_url[:35]}...")
                        success, msg = self.engine.comment_on_tweet(post_url, comment_text)

                        if success:
                            consecutive_errors = 0
                            commented_this_round += 1
                            log_x_comment(post_url, post_content, comment_text, status="Đã gửi")
                            self.notify_ui("x_status", f"Đã gửi cmt thành công lên Tweet 𝕏: {post_url[:35]}...")

                            # Bắn thông báo Telegram
                            if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("x_telegram_alerts_enabled", "1") == "1":
                                today_count = self.count_today_comments()
                                daily_limit = int(get_setting("x_daily_limit", "100"))
                                TelegramNotifier.notify_x_comment(
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
                            min_delay = int(get_setting("x_min_delay", "110"))
                            max_delay = int(get_setting("x_max_delay", "130"))
                            chosen_delay = random.randint(min_delay, max_delay)

                            for remaining in range(chosen_delay, 0, -1):
                                if not self.is_running:
                                    break
                                mins = remaining // 60
                                secs = remaining % 60
                                self.notify_ui("x_countdown", f"chờ Tweet tiếp theo: {mins}:{secs:02d}")
                                time.sleep(1)
                            self.notify_ui("x_countdown", "")

                        else:
                            consecutive_errors += 1
                            log_x_comment(post_url, post_content, comment_text, status="Lỗi", error=msg)
                            self.notify_ui("x_status", f"Lỗi cmt 𝕏: {msg}")

                            if consecutive_errors >= 4:
                                self.notify_ui("x_status", "Phát hiện 4 lỗi liên tiếp. Dừng bot 𝕏 để bảo vệ tài khoản.")
                                if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("x_telegram_alerts_enabled", "1") == "1":
                                    TelegramNotifier.send_message(f"⚠️ <b>[𝕏 Bot Cảnh Báo]</b> 4 lỗi liên tiếp ({msg}). Đã tự dừng!")
                                self.stop()
                                return

                            time.sleep(15)

                    if commented_this_round == 0 and self.is_running:
                        scan_interval = int(get_setting("x_scan_interval", "2"))
                        self.notify_ui("x_status", f"Lượt cào vừa rồi đã xong hoặc chưa có tweet mới. Lần cào tiếp sau {scan_interval} phút...")
                        wait_seconds = max(15, scan_interval * 60)
                        for remaining in range(wait_seconds, 0, -1):
                            if not self.is_running:
                                break
                            mins = remaining // 60
                            secs = remaining % 60
                            self.notify_ui("x_countdown", f"cào đợt tiếp: {mins}:{secs:02d}")
                            time.sleep(1)
                        self.notify_ui("x_countdown", "")

            except Exception as e:
                err_text = str(e)
                print("Lỗi tiến trình 𝕏 Worker:", err_text)
                self.notify_ui("x_status", f"Lỗi 𝕏: {err_text}")
            finally:
                if self.engine:
                    try:
                        self.engine.close()
                    except Exception:
                        pass
                    self.engine = None
                self.is_running = False
                self.notify_ui("x_auto_state_changed", False)
                self.notify_ui("x_countdown", "")
                self.notify_ui("x_status", "Hệ thống 𝕏 (Twitter) Auto Bot đã dừng.")

        self.worker_thread = threading.Thread(target=_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Dừng tiến trình 𝕏"""
        self.is_running = False
        self.notify_ui("x_auto_state_changed", False)
        self.notify_ui("x_countdown", "")
        self.notify_ui("x_status", "Đang dừng 𝕏 (Twitter) Auto Bot...")
        if self.engine:
            try:
                self.engine.close()
            except Exception:
                pass
            self.engine = None

