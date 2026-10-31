import os
import sys

# Đảm bảo hiển thị tiếng Việt mượt mà trên console Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import webbrowser
import webview
from datetime import datetime
from core.db import (
    init_db, get_setting, set_setting, get_all_settings,
    get_recent_logs, log_comment, add_target_url
)
from core.ai_engine import AIEngine
from core.browser_engine import BrowserEngine
from core.bot_worker import BotWorker

class DesktopAPI:
    def __init__(self):
        self.live_status = "Hệ thống sẵn sàng."
        self.countdown_text = ""
        self.worker = BotWorker(ui_callback=self._on_worker_event)
        self.login_browser = None

    def _on_worker_event(self, event_type, data):
        if event_type == "status":
            self.live_status = str(data)
        elif event_type == "countdown":
            self.countdown_text = str(data)
        elif event_type == "auto_state_changed":
            if not data:
                self.countdown_text = ""

    def get_settings(self):
        return get_all_settings()

    def save_settings(self, settings_dict):
        for k, v in settings_dict.items():
            set_setting(k, v)
        return True

    def set_setting(self, key, value):
        set_setting(key, value)
        return True

    def test_gemini(self, api_key):
        return AIEngine.test_gemini_connection(api_key)

    def open_login_browser(self):
        """Mở cửa sổ Chrome thật để người dùng tự do đăng nhập và quản lý Fanpage an toàn"""
        if self.login_browser is None:
            self.login_browser = BrowserEngine(headless=False)
        self.login_browser.open_for_login()
        self.live_status = "Đang mở trình duyệt đăng nhập Facebook..."
        return True

    def check_login_status(self):
        b = BrowserEngine(headless=True)
        is_logged = b.check_is_logged_in()
        b.close()
        return {"is_logged_in": is_logged}

    def scan_test(self):
        if self.login_browser:
            self.login_browser.close()
            self.login_browser = None
        self.worker.scan_only()
        return True

    def start_auto(self):
        if self.login_browser:
            self.login_browser.close()
            self.login_browser = None
        self.worker.start_auto()
        return True

    def stop_auto(self):
        self.worker.stop()
        return True

    def get_state(self):
        """Được UI gọi định kỳ để lấy trạng thái thời gian thực"""
        logs = get_recent_logs(limit=40)
        # Nếu đang có kết quả quét thử mới nhất thì gộp vào đầu
        if self.worker.last_scanned_posts:
            logs = self.worker.last_scanned_posts + logs

        # Đếm số bình luận hôm nay
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for l in logs if l.get("status") == "Đã gửi" and str(l.get("created_at", "")).startswith(today_str))

        return {
            "is_auto_running": self.worker.is_running,
            "live_status": self.live_status,
            "countdown": self.countdown_text,
            "logs": logs,
            "today_count": today_count
        }

    def open_url_external(self, url):
        webbrowser.open(url)
        return True

    def send_manual_comment(self, post_url, comment_text):
        b = BrowserEngine(headless=False)
        success, msg = b.comment_on_post(post_url, comment_text)
        b.close()
        if success:
            log_comment(post_url, "Bình luận thủ công", comment_text, "Fanpage", "Đã gửi")
        return {"success": success, "message": msg}

    def add_target_url(self, url):
        if url and url.strip():
            add_target_url(url.strip())
            return True
        return False

def main():
    # 1. Khởi tạo cơ sở dữ liệu SQLite
    init_db()

    # 2. Khởi tạo API kết nối giao diện
    api = DesktopAPI()

    # 3. Đường dẫn giao diện HTML
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")

    # 4. Tạo cửa sổ Desktop ứng dụng
    window = webview.create_window(
        title="Facebook Page Auto Commenter - Pro Edition",
        url=web_dir,
        js_api=api,
        width=1240,
        height=820,
        min_size=(1050, 680),
        background_color="#0d0d11"
    )

    # 5. Khởi động GUI với Edge Chromium (WebView2)
    webview.start(debug=False)

if __name__ == "__main__":
    main()
