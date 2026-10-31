import time
import random
import threading
from datetime import datetime
from core.db import (
    get_setting, set_setting, log_comment, 
    is_post_already_commented, get_recent_logs,
    get_pending_target_urls, mark_post_status
)
from core.ai_engine import AIEngine
from core.browser_engine import BrowserEngine

class BotWorker:
    def __init__(self, ui_callback=None):
        self.is_running = False
        self.worker_thread = None
        self.ui_callback = ui_callback
        self.browser = None
        self.last_scanned_posts = []

    def notify_ui(self, event_type, data):
        """Gửi thông báo cập nhật về giao diện"""
        if self.ui_callback:
            try:
                self.ui_callback(event_type, data)
            except Exception as e:
                print("Lỗi callback UI:", str(e))

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

    def scan_only(self):
        """Chức năng 'Quét thử - chưa gửi' để xem trước danh sách bài và cmt dự kiến"""
        def _job():
            self.notify_ui("status", "Đang mở trình duyệt quét bài...")
            browser = BrowserEngine(headless=False)
            try:
                posts = browser.scan_newsfeed_posts(max_posts=5)
                self.last_scanned_posts = []
                for p in posts:
                    # Tạo bình luận mẫu bằng AI
                    predicted_comment = AIEngine.generate_comment(p["content"])
                    item = {
                        "url": p["url"],
                        "content": p["content"],
                        "predicted_comment": predicted_comment,
                        "status": "Chưa gửi (Quét thử)"
                    }
                    self.last_scanned_posts.append(item)
                    self.notify_ui("new_post_scanned", item)
                self.notify_ui("status", f"Quét thử hoàn tất. Tìm thấy {len(self.last_scanned_posts)} bài viết.")
            except Exception as e:
                self.notify_ui("status", f"Lỗi quét thử: {str(e)}")
            finally:
                browser.close()

        threading.Thread(target=_job, daemon=True).start()

    def start_auto(self):
        """Bắt đầu chu trình tự động bình luận theo lịch"""
        if self.is_running:
            return

        self.is_running = True
        set_setting("auto_comment_enabled", "1")
        self.notify_ui("auto_state_changed", True)

        def _loop():
            self.browser = BrowserEngine(headless=False)
            self.notify_ui("status", "Hệ thống tự động bình luận đã khởi động...")

            while self.is_running:
                if not self.check_active_time():
                    self.notify_ui("status", "Đang ngoài khung giờ hoạt động. Tạm nghỉ 10 phút...")
                    for _ in range(600):
                        if not self.is_running:
                            break
                        time.sleep(1)
                    continue

                source_type = get_setting("feed_source", "for_you")
                posts = []

                if source_type == "custom_urls":
                    self.notify_ui("status", "Đang lấy danh sách bài viết từ URL chỉ định...")
                    pending_targets = get_pending_target_urls(limit=5)
                    for item in pending_targets:
                        target_url = item["post_url"]
                        self.notify_ui("status", f"Đang trích xuất nội dung bài: {target_url[:35]}...")
                        content = self.browser.extract_single_post_content(target_url)
                        posts.append({
                            "url": target_url,
                            "content": content,
                            "source": "Custom URL"
                        })
                else:
                    self.notify_ui("status", "Đang quét bài viết mới trên Facebook...")
                    posts = self.browser.scan_newsfeed_posts(max_posts=6)

                # Lọc bài theo từ khóa nếu có cấu hình
                keywords_raw = get_setting("keywords", "").strip()
                keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]

                for p in posts:
                    if not self.is_running:
                        break

                    post_content = p["content"]
                    post_url = p["url"]

                    # Kiểm tra từ khóa
                    if keywords:
                        has_kw = any(kw in post_content.lower() for kw in keywords)
                        if not has_kw:
                            continue

                    if is_post_already_commented(post_url):
                        continue

                    # Sinh bình luận thông minh bằng Gemini / Spintax
                    self.notify_ui("status", "AI đang phân tích ngữ cảnh bài viết...")
                    comment_text = AIEngine.generate_comment(post_content)

                    # Gửi thông tin về UI
                    self.notify_ui("current_processing", {
                        "url": post_url,
                        "snippet": post_content,
                        "comment": comment_text
                    })

                    # Thực hiện bình luận trên trình duyệt
                    self.notify_ui("status", f"Đang mô phỏng người thật bình luận vào bài: {post_url[:35]}...")
                    success, msg = self.browser.comment_on_post(post_url, comment_text)

                    status_str = "Đã gửi" if success else "Lỗi"
                    log_comment(post_url, post_content[:100], comment_text, "Fanpage", status_str, msg)
                    mark_post_status(post_url, "sent" if success else "failed")

                    self.notify_ui("comment_completed", {
                        "post_snippet": post_content[:80],
                        "comment_content": comment_text,
                        "status": status_str,
                        "time": datetime.now().strftime("%H:%M:%S")
                    })

                    # Nghỉ ngẫu nhiên giữa 2 lần bình luận (Jitter)
                    min_d = int(get_setting("min_delay", "120"))
                    max_d = int(get_setting("max_delay", "300"))
                    delay_time = random.randint(min_d, max_d)

                    for sec in range(delay_time, 0, -1):
                        if not self.is_running:
                            break
                        self.notify_ui("countdown", f"Chờ bài tiếp theo: {sec}s")
                        time.sleep(1)

                # Sau khi hết lượt bài, chờ theo scan_interval
                scan_minutes = int(get_setting("scan_interval", "5"))
                self.notify_ui("status", f"Đã quét xong lượt này. Lần quét tiếp theo sau {scan_minutes} phút...")
                for sec in range(scan_minutes * 60, 0, -1):
                    if not self.is_running:
                        break
                    time.sleep(1)

            if self.browser:
                self.browser.close()
            self.notify_ui("status", "Đã dừng tự động bình luận.")

        self.worker_thread = threading.Thread(target=_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Dừng tác vụ tự động"""
        self.is_running = False
        set_setting("auto_comment_enabled", "0")
        self.notify_ui("auto_state_changed", False)
        self.notify_ui("status", "Đang gửi lệnh dừng...")
        if self.browser:
            self.browser.close()

