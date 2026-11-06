import os
import sys

# Khắc phục lỗi khi chạy ngầm qua pythonw.exe (tránh lỗi sys.stdout và sys.stderr là None)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
elif hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')
elif hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import json
import webbrowser
import webview
from datetime import datetime
from core.db import (
    init_db, get_setting, set_setting, get_all_settings,
    get_recent_logs, log_comment, add_target_url, export_logs_to_csv,
    get_fanpages, save_fanpage, set_selected_fanpage, get_selected_fanpage,
    get_recent_threads_logs, log_threads_comment, export_threads_logs_to_csv,
    get_recent_x_logs, log_x_comment, export_x_logs_to_csv
)
from core.ai_engine import AIEngine
from core.browser_engine import BrowserEngine
from core.bot_worker import BotWorker
from core.threads_engine import ThreadsEngine
from core.threads_worker import ThreadsWorker
from core.x_engine import XEngine
from core.x_worker import XWorker
from core.telegram_notifier import TelegramNotifier

class DesktopAPI:
    def __init__(self):
        self.live_status = "Hệ thống sẵn sàng."
        self.countdown_text = ""
        self.worker = BotWorker(ui_callback=self._on_worker_event)
        self.login_browser = None

        # Threads State
        self.threads_live_status = "Hệ thống Threads sẵn sàng."
        self.threads_countdown_text = ""
        self.threads_worker = ThreadsWorker(ui_callback=self._on_threads_worker_event)

        # X (Twitter) State
        self.x_live_status = "Hệ thống 𝕏 (Twitter) sẵn sàng."
        self.x_countdown_text = ""
        self.x_worker = XWorker(ui_callback=self._on_x_worker_event)

    def _on_worker_event(self, event_type, data):
        if event_type == "status":
            self.live_status = str(data)
        elif event_type == "countdown":
            self.countdown_text = str(data)
        elif event_type == "auto_state_changed":
            if not data:
                self.countdown_text = ""

    def _on_threads_worker_event(self, event_type, data):
        if event_type == "threads_status":
            self.threads_live_status = str(data)
        elif event_type == "threads_countdown":
            self.threads_countdown_text = str(data)
        elif event_type == "threads_auto_state_changed":
            if not data:
                self.threads_countdown_text = ""

    def _on_x_worker_event(self, event_type, data):
        if event_type == "x_status":
            self.x_live_status = str(data)
        elif event_type == "x_countdown":
            self.x_countdown_text = str(data)
        elif event_type == "x_auto_state_changed":
            if not data:
                self.x_countdown_text = ""

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

    def test_telegram(self, bot_token, chat_id):
        success, msg = TelegramNotifier.test_connection(bot_token, chat_id)
        return {"success": success, "message": msg}

    def test_proxy(self, proxy_str):
        return BrowserEngine.test_proxy(proxy_str)

    def get_fanpages_list(self):
        pages = get_fanpages()
        selected = get_selected_fanpage()
        return {"pages": pages, "selected": selected}

    def add_fanpage(self, name, url=""):
        if name and name.strip():
            save_fanpage(name.strip(), url.strip(), is_selected=1)
            set_selected_fanpage(name.strip())
            return {"success": True, "name": name.strip()}
        return {"success": False, "message": "Tên Fanpage không được để trống"}

    def select_fanpage(self, name):
        set_selected_fanpage(name)
        return True

    def scan_fanpages_from_facebook(self):
        self.live_status = "Đang quét danh sách Fanpage từ tài khoản..."
        b = BrowserEngine(headless=False)
        pages = b.scan_managed_fanpages()
        b.close()
        for p in pages:
            save_fanpage(p["name"], p["url"])
        if pages:
            set_selected_fanpage(pages[0]["name"])
        self.live_status = f"Đã quét xong {len(pages)} Fanpage."
        return {"success": True, "count": len(pages), "pages": get_fanpages(), "selected": get_selected_fanpage()}

    def open_login_browser(self):
        """Mở cửa sổ Chrome thật để người dùng tự do đăng nhập và quản lý Fanpage an toàn"""
        if self.login_browser:
            self.login_browser.close()
            self.login_browser = None
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

    def add_bulk_target_urls(self, urls_text):
        """Thêm hàng loạt link bài viết từ danh sách cách nhau bằng xuống dòng"""
        lines = [u.strip() for u in urls_text.split("\n") if u.strip().startswith("http")]
        for u in lines:
            add_target_url(u)
        return len(lines)

    def export_csv(self):
        """Xuất lịch sử cmt ra file CSV và mở vị trí file"""
        path = export_logs_to_csv()
        return {"success": True, "path": path}

    # ==================== THREADS API ====================
    def open_threads_login_browser(self):
        """Mở cửa sổ Chrome thật với User Data riêng biệt cho Threads để đăng nhập"""
        if self.threads_worker.is_running:
            self.threads_worker.stop()
        engine = ThreadsEngine(headless=False)
        engine.open_for_login()
        self.threads_live_status = "Đang mở trình duyệt Chrome đăng nhập Threads..."
        return True

    def check_threads_login_status(self):
        if ThreadsEngine.check_cookie_login():
            return {"is_logged_in": True}
        engine = ThreadsEngine(headless=True)
        is_logged = engine.check_is_logged_in()
        engine.close()
        return {"is_logged_in": is_logged}

    def scan_threads_test(self):
        self.threads_worker.scan_only()
        return True

    def start_threads_auto(self):
        self.threads_worker.start_auto()
        return True

    def stop_threads_auto(self):
        self.threads_worker.stop()
        return True

    def get_threads_state(self):
        logs = get_recent_threads_logs(limit=40)
        if self.threads_worker.last_scanned_posts:
            logs = self.threads_worker.last_scanned_posts + logs
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for l in logs if l.get("status") == "Đã gửi" and str(l.get("created_at", "")).startswith(today_str))
        return {
            "is_auto_running": self.threads_worker.is_running,
            "live_status": self.threads_live_status,
            "countdown": self.threads_countdown_text,
            "logs": logs,
            "today_count": today_count
        }

    def send_threads_manual_comment(self, post_url, comment_text):
        engine = ThreadsEngine(headless=False)
        success, msg = engine.comment_on_thread(post_url, comment_text)
        engine.close()
        if success:
            log_threads_comment(post_url, "Bình luận thủ công", comment_text, status="Đã gửi")
            if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("threads_telegram_alerts_enabled", "1") == "1":
                today_count = self.threads_worker.count_today_comments()
                daily_limit = int(get_setting("threads_daily_limit", "30"))
                TelegramNotifier.notify_threads_comment(
                    post_url=post_url,
                    post_content="Bình luận gửi thủ công từ bảng điều khiển",
                    comment_text=comment_text,
                    author="Thủ công",
                    is_general=False,
                    is_manual=True,
                    today_count=today_count,
                    daily_limit=daily_limit
                )
        return {"success": success, "message": msg}

    def test_threads_telegram(self):
        token = get_setting("telegram_bot_token", "")
        chat_id = get_setting("telegram_chat_id", "")
        if not token or not chat_id:
            return {"success": False, "message": "Chưa có Token hoặc Chat ID. Vui lòng nhập vào mục Cài đặt."}
        success, msg = TelegramNotifier.test_threads_connection(token, chat_id)
        return {"success": success, "message": msg}

    def toggle_threads_telegram_alerts(self):
        curr = get_setting("threads_telegram_alerts_enabled", "1")
        new_val = "0" if curr == "1" else "1"
        set_setting("threads_telegram_alerts_enabled", new_val)
        return {"success": True, "enabled": (new_val == "1")}

    def export_threads_csv(self):
        path = export_threads_logs_to_csv()
        return {"success": True, "path": path}

    # ==================== 𝕏 (TWITTER) API ====================
    def open_x_login_browser(self):
        """Mở cửa sổ Chrome thật với User Data riêng biệt cho 𝕏 để đăng nhập"""
        if self.x_worker.is_running:
            self.x_worker.stop()
        engine = XEngine(headless=False)
        engine.open_for_login()
        self.x_live_status = "Đang mở trình duyệt Chrome đăng nhập 𝕏..."
        return True

    def check_x_login_status(self):
        if XEngine.check_cookie_login():
            return {"is_logged_in": True}
        engine = XEngine(headless=True)
        is_logged = engine.check_is_logged_in()
        engine.close()
        return {"is_logged_in": is_logged}

    def scan_x_test(self):
        self.x_worker.scan_only()
        return True

    def start_x_auto(self):
        self.x_worker.start_auto()
        return True

    def stop_x_auto(self):
        self.x_worker.stop()
        return True

    def get_x_state(self):
        logs = get_recent_x_logs(limit=40)
        if self.x_worker.last_scanned_posts:
            logs = self.x_worker.last_scanned_posts + logs
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for l in logs if l.get("status") == "Đã gửi" and str(l.get("created_at", "")).startswith(today_str))
        return {
            "is_auto_running": self.x_worker.is_running,
            "live_status": self.x_live_status,
            "countdown": self.x_countdown_text,
            "logs": logs,
            "today_count": today_count
        }

    def send_x_manual_comment(self, post_url, comment_text):
        engine = XEngine(headless=False)
        success, msg = engine.comment_on_tweet(post_url, comment_text)
        engine.close()
        if success:
            log_x_comment(post_url, "Bình luận thủ công", comment_text, status="Đã gửi")
            if get_setting("telegram_alerts_enabled", "1") == "1" or get_setting("x_telegram_alerts_enabled", "1") == "1":
                today_count = self.x_worker.count_today_comments()
                daily_limit = int(get_setting("x_daily_limit", "100"))
                TelegramNotifier.notify_x_comment(
                    post_url=post_url,
                    post_content="Bình luận gửi thủ công từ bảng điều khiển",
                    comment_text=comment_text,
                    author="Thủ công",
                    is_general=False,
                    is_manual=True,
                    today_count=today_count,
                    daily_limit=daily_limit
                )
        return {"success": success, "message": msg}

    def test_x_telegram(self):
        token = get_setting("telegram_bot_token", "")
        chat_id = get_setting("telegram_chat_id", "")
        if not token or not chat_id:
            return {"success": False, "message": "Chưa có Token hoặc Chat ID. Vui lòng nhập vào mục Cài đặt."}
        success, msg = TelegramNotifier.test_x_connection(token, chat_id)
        return {"success": success, "message": msg}

    def toggle_x_telegram_alerts(self):
        curr = get_setting("x_telegram_alerts_enabled", "1")
        new_val = "0" if curr == "1" else "1"
        set_setting("x_telegram_alerts_enabled", new_val)
        return {"success": True, "enabled": (new_val == "1")}

    def export_x_csv(self):
        path = export_x_logs_to_csv()
        return {"success": True, "path": path}

def main():
    # 1. Khởi tạo cơ sở dữ liệu SQLite
    init_db()

    # 2. Khởi tạo API kết nối giao diện
    api = DesktopAPI()

    # 3. Đường dẫn giao diện HTML
    web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "index.html")

    # 4. Tạo cửa sổ Desktop ứng dụng
    window = webview.create_window(
        title="Facebook, Threads & 𝕏 (Twitter) Auto Commenter - Pro Edition",
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
