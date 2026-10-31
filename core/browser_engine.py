import os
import sys
import time
import random
import asyncio
from playwright.sync_api import sync_playwright
from core.db import get_setting, log_comment, is_post_already_commented

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_data")
os.makedirs(DATA_DIR, exist_ok=True)

class BrowserEngine:
    _active_instance = None

    @staticmethod
    def get_system_chrome_path():
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    @staticmethod
    def parse_proxy(proxy_str):
        """Chuẩn hóa cấu hình proxy hỗ trợ IP:Port:User:Pass hoặc http://..."""
        if not proxy_str or not proxy_str.strip():
            return None
        proxy_str = proxy_str.strip()
        parts = proxy_str.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            return {
                "server": f"http://{ip}:{port}",
                "username": user,
                "password": pwd
            }
        if "@" in proxy_str:
            clean = proxy_str.replace("http://", "").replace("https://", "")
            auth, host = clean.split("@")
            user, pwd = auth.split(":")
            return {
                "server": f"http://{host}",
                "username": user,
                "password": pwd
            }
        if not proxy_str.startswith("http"):
            proxy_str = f"http://{proxy_str}"
        return {"server": proxy_str}

    @staticmethod
    def test_proxy(proxy_str):
        """Kiểm tra địa chỉ IP thực tế qua Proxy"""
        cfg = BrowserEngine.parse_proxy(proxy_str)
        if not cfg:
            return {"success": False, "message": "Định dạng Proxy không hợp lệ"}
        try:
            if "username" in cfg and "password" in cfg:
                server = cfg["server"].replace("http://", "")
                proxies = {
                    "http": f"http://{cfg['username']}:{cfg['password']}@{server}",
                    "https": f"http://{cfg['username']}:{cfg['password']}@{server}"
                }
            else:
                proxies = {
                    "http": cfg["server"],
                    "https": cfg["server"]
                }
            resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
            if resp.status_code == 200:
                ip = resp.json().get("ip", "")
                return {"success": True, "ip": ip, "message": f"Proxy hoạt động! IP mới: {ip}"}
            return {"success": False, "message": f"Proxy phản hồi mã {resp.status_code}"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi kết nối Proxy: {str(e)}"}

    def __init__(self, headless=False, proxy=None):
        self.headless = headless
        # Tự động lấy proxy từ settings nếu không truyền vào
        if not proxy:
            proxy = get_setting("proxy_string", "")
        self.proxy = proxy
        self.playwright = None
        self.context = None
        self.page = None

    def start(self):
        """Khởi động trình duyệt với user-data-dir để lưu trữ session vĩnh viễn"""
        # Nếu có instance trước đó đang giữ lock, đóng trước
        if BrowserEngine._active_instance and BrowserEngine._active_instance != self:
            try:
                BrowserEngine._active_instance.close()
            except Exception:
                pass

        if self.playwright is None:
            self.playwright = sync_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--lang=vi-VN,vi,en-US,en"
        ]

        proxy_config = BrowserEngine.parse_proxy(self.proxy)

        chrome_path = BrowserEngine.get_system_chrome_path()
        channel = "chrome" if chrome_path else None

        launch_kwargs = {
            "user_data_dir": DATA_DIR,
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "locale": "vi-VN",
            "timezone_id": "Asia/Ho_Chi_Minh",
            "proxy": proxy_config,
            "ignore_default_args": ["--enable-automation"],
            "args": args
        }
        if channel:
            launch_kwargs["channel"] = channel

        self.context = self.playwright.chromium.launch_persistent_context(**launch_kwargs)

        BrowserEngine._active_instance = self

        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        # Áp dụng stealth script tránh phát hiện bot
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        return self.page

    def close(self):
        """Đóng an toàn trình duyệt"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            if BrowserEngine._active_instance == self:
                BrowserEngine._active_instance = None
            self.context = None
            self.playwright = None
            self.page = None

    def open_for_login(self):
        """Mở trình duyệt trực quan để người dùng tự đăng nhập và vượt 2FA (dùng Chrome thật không dính cờ bot Arkose Labs)"""
        self.close()
        chrome_path = BrowserEngine.get_system_chrome_path()
        if chrome_path:
            import subprocess
            subprocess.Popen([
                chrome_path,
                f"--user-data-dir={DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                "https://www.facebook.com"
            ])
            return True
        else:
            self.headless = False
            self.start()
            self.page.goto("https://www.facebook.com", timeout=60000)
            return True

    def check_is_logged_in(self):
        """Kiểm tra tài khoản đã đăng nhập Facebook hay chưa"""
        try:
            if not self.page:
                self.start()
            self.page.goto("https://www.facebook.com", timeout=30000)
            time.sleep(3)
            current_url = self.page.url
            if "login" in current_url:
                return False
            # Tìm avatar hoặc nút tạo bài viết
            has_feed = self.page.locator('div[role="feed"]').count() > 0 or \
                       self.page.locator('div[aria-label="Tài khoản của bạn"]').count() > 0 or \
                       self.page.locator('div[aria-label="Your profile"]').count() > 0
            return has_feed
        except Exception:
            return False

    def scan_newsfeed_posts(self, max_posts=10):
        """Quét các bài viết trên Newsfeed Facebook"""
        if not self.page:
            self.start()

        posts = []
        try:
            self.page.goto("https://www.facebook.com", timeout=45000)
            time.sleep(4)

            # Cuộn trang nhẹ nhàng 2-3 lần để load thêm bài viết
            for _ in range(3):
                self.page.evaluate("window.scrollBy(0, 600)")
                time.sleep(random.uniform(1.5, 2.5))

            articles = self.page.locator('div[role="feed"] > div').all()
            for article in articles:
                if len(posts) >= max_posts:
                    break

                # Trích xuất nội dung bài viết
                text = article.inner_text().strip()
                if len(text) < 25:
                    continue

                # Lọc bỏ các bài viết quảng cáo hoặc bài gợi ý nếu muốn
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                # Bỏ các nút Thích, Bình luận, Chia sẻ ở cuối
                filtered_lines = [l for l in lines if l not in ["Thích", "Bình luận", "Chia sẻ", "Gửi", "Like", "Comment", "Share"]]
                clean_text = " ".join(filtered_lines[:10])

                # Tìm link bài viết
                post_url = ""
                links = article.locator("a").all()
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "/posts/" in href or "/videos/" in href or "story_fbid=" in href or "/photo" in href:
                        post_url = href.split("?")[0]
                        if not post_url.startswith("http"):
                            post_url = "https://www.facebook.com" + post_url
                        break

                if not post_url:
                    # Nếu không tìm thấy link riêng, tạo id giả lập theo snippet
                    post_url = f"https://www.facebook.com/post_snippet_{abs(hash(clean_text[:60]))}"

                # Tìm ảnh đính kèm bài viết nếu có (cho Gemini Multimodal Vision)
                img_url = ""
                try:
                    for img in article.locator("img").all():
                        src = img.get_attribute("src") or ""
                        if "scontent" in src or "fbcdn" in src:
                            img_url = src
                            break
                except Exception:
                    pass

                if not is_post_already_commented(post_url):
                    posts.append({
                        "url": post_url,
                        "content": clean_text[:400],
                        "image_url": img_url,
                        "source": "Newsfeed"
                    })
        except Exception as e:
            print("Lỗi khi quét Newsfeed:", str(e))

        return posts

    def human_type(self, locator, text):
        """Gõ chữ mô phỏng hành vi người thật với độ trễ biến thiên"""
        for char in text:
            locator.type(char, delay=random.randint(45, 120))
            if random.random() < 0.05:
                # Thỉnh thoảng khựng lại 0.2 - 0.4s như người đang suy nghĩ
                time.sleep(random.uniform(0.2, 0.4))

    def comment_on_post(self, post_url, comment_text, fanpage_name=""):
        """Thực hiện bình luận vào bài viết chỉ định"""
        if not self.page:
            self.start()

        try:
            self.page.goto(post_url, timeout=45000)
            time.sleep(random.uniform(3, 5))

            # Cuộn nhẹ trang như người đang đọc
            self.page.evaluate(f"window.scrollBy(0, {random.randint(200, 450)})")
            time.sleep(random.uniform(2, 4))

            # Thả Like nhẹ như người dùng thật (Warm-up Like chống bot detection)
            auto_like = get_setting("auto_like_enabled", "1") == "1"
            if auto_like:
                try:
                    like_btn = self.page.locator('div[aria-label="Thích"], div[aria-label="Like"], div[role="button"]:has-text("Thích")').first
                    if like_btn.count() > 0 and like_btn.is_visible():
                        like_btn.click()
                        time.sleep(random.uniform(1.2, 2.5))
                except Exception:
                    pass

            # Tìm ô bình luận trên Facebook (hỗ trợ nhiều selector)
            comment_selectors = [
                'div[aria-label*="Viết bình luận"]',
                'div[aria-label*="Write a comment"]',
                'div[aria-label*="Bình luận dưới tên"]',
                'div[role="textbox"][contenteditable="true"]',
                'form [role="textbox"]'
            ]

            input_box = None
            for sel in comment_selectors:
                loc = self.page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    input_box = loc
                    break

            if not input_box:
                return False, "Không tìm thấy ô nhập bình luận trên bài viết này"

            # Di chuột và click vào ô nhập
            input_box.click()
            time.sleep(random.uniform(1.0, 2.0))

            # Gõ nội dung bình luận
            self.human_type(input_box, comment_text)
            time.sleep(random.uniform(1.2, 2.5))

            # Nhấn Enter để gửi
            self.page.keyboard.press("Enter")
            time.sleep(random.uniform(3, 5))

            return True, "Bình luận thành công"

        except Exception as e:
            return False, f"Lỗi thao tác: {str(e)}"

    def reply_to_comment_on_post(self, post_url, comment_text):
        """Ưu tiên trả lời (Reply) trực tiếp vào bình luận của người hỏi để bắn thông báo chuông"""
        if not self.page:
            self.start()

        try:
            self.page.goto(post_url, timeout=45000)
            time.sleep(random.uniform(3, 5))

            # Cuộn xuống phần bình luận
            self.page.evaluate(f"window.scrollBy(0, {random.randint(300, 550)})")
            time.sleep(random.uniform(2, 3))

            # Tìm nút "Phản hồi" hoặc "Reply" của bình luận đầu tiên
            reply_buttons = self.page.locator('div[role="button"]:has-text("Phản hồi"), div[role="button"]:has-text("Reply")').all()
            if reply_buttons and len(reply_buttons) > 0:
                # Chọn nút phản hồi đầu tiên
                target_btn = reply_buttons[0]
                target_btn.click()
                time.sleep(random.uniform(1.2, 2.0))

                # Tìm ô nhập reply vừa mở
                reply_input = self.page.locator('div[role="textbox"][contenteditable="true"]').last
                if reply_input.count() > 0:
                    reply_input.click()
                    time.sleep(1)
                    self.human_type(reply_input, comment_text)
                    time.sleep(random.uniform(1.2, 2.0))
                    self.page.keyboard.press("Enter")
                    time.sleep(random.uniform(3, 4))
                    return True, "Trả lời (Reply) bình luận thành công"

            # Nếu bài chưa có cmt để reply, tự động fallback sang bình luận trực tiếp bài viết
            return self.comment_on_post(post_url, comment_text)

        except Exception as e:
            # Fallback sang comment bình thường nếu gặp lỗi
            return self.comment_on_post(post_url, comment_text)

    def extract_single_post_content(self, post_url):
        """Mở 1 link bài viết cụ thể và trích xuất nội dung bài viết kèm ảnh (nếu có)"""
        if not self.page:
            self.start()

        try:
            self.page.goto(post_url, timeout=45000)
            time.sleep(random.uniform(3, 5))

            img_url = ""
            try:
                for img in self.page.locator('div[role="article"] img, div[data-ad-preview] img').all():
                    src = img.get_attribute("src") or ""
                    if "scontent" in src or "fbcdn" in src:
                        img_url = src
                        break
            except Exception:
                pass

            # Tìm nội dung bài viết
            selectors = [
                'div[data-ad-preview="message"]',
                'div[dir="auto"]',
                'div[role="article"]'
            ]
            for sel in selectors:
                loc = self.page.locator(sel).first
                if loc.count() > 0:
                    text = loc.inner_text().strip()
                    if len(text) > 15:
                        return {"content": text[:500], "image_url": img_url}

            # Fallback lấy text trên body
            body_text = self.page.locator('body').inner_text()
            return {"content": body_text[:300], "image_url": img_url}
        except Exception as e:
            return {"content": f"Không thể lấy nội dung bài viết: {str(e)}", "image_url": ""}

    def run_warmup(self, duration_sec=60):
        """Mô phỏng người thật lướt xem tin tức 60s để làm ấm session (Pre-Action Warm-Up)"""
        if not self.page:
            self.start()
        try:
            self.page.goto("https://www.facebook.com", timeout=30000)
            time.sleep(3)
            start = time.time()
            while time.time() - start < duration_sec:
                scroll_y = random.randint(300, 600)
                self.page.evaluate(f"window.scrollBy(0, {scroll_y})")
                time.sleep(random.uniform(3.5, 7.0))
                if random.random() < 0.3:
                    self.page.evaluate("window.scrollBy(0, -200)")
                    time.sleep(random.uniform(2.0, 4.0))
            return True
        except Exception:
            return False

    def switch_to_fanpage(self, page_name=""):
        """Hỗ trợ tự động chuyển đổi sang Profile Fanpage (New Page Experience) hoàn toàn tự động"""
        if not self.page:
            self.start()

        if not page_name:
            return True, "Không có tên Fanpage"

        try:
            self.page.goto("https://www.facebook.com", timeout=35000)
            time.sleep(3)

            # 1. Kiểm tra xem hiện tại có thể đã là Fanpage này chưa
            try:
                banner_text = self.page.locator('div[role="banner"]').inner_text()
                if page_name.lower() in banner_text.lower():
                    return True, f"Hiện tại đã là Fanpage {page_name}"
            except Exception:
                pass

            # 2. Click vào Avatar menu góc trên bên phải
            avatar_selectors = [
                'div[aria-label*="Tài khoản của bạn"]',
                'div[aria-label*="Your profile"]',
                'div[aria-label*="Trang cá nhân"]',
                'div[role="banner"] [role="button"]:has(svg)',
                'div[role="banner"] [role="button"]:has(image)'
            ]
            avatar_clicked = False
            for sel in avatar_selectors:
                btn = self.page.locator(sel).first
                if btn.count() > 0 and btn.is_visible():
                    btn.click()
                    avatar_clicked = True
                    time.sleep(2)
                    break

            if avatar_clicked:
                # Tìm nút "Xem tất cả trang cá nhân" hoặc "See all profiles"
                see_all = self.page.locator('div[role="button"]:has-text("Xem tất cả"), div[role="button"]:has-text("See all"), div[aria-label*="Xem tất cả"]').first
                if see_all.count() > 0 and see_all.is_visible():
                    see_all.click()
                    time.sleep(2)

                # Tìm và click vào Fanpage mục tiêu theo tên
                target_selectors = [
                    f'div[role="button"]:has-text("{page_name}")',
                    f'div[role="listitem"]:has-text("{page_name}")',
                    f'span:has-text("{page_name}")'
                ]
                for tsel in target_selectors:
                    target_page = self.page.locator(tsel).first
                    if target_page.count() > 0 and target_page.is_visible():
                        target_page.click()
                        time.sleep(5)
                        return True, f"Đã tự động chuyển sang Fanpage: {page_name}"

            return True, "Giữ nguyên profile hiện tại"
        except Exception as e:
            return False, f"Không thể tự động switch page: {str(e)}"

    def scan_managed_fanpages(self):
        """Tự động quét danh sách các Fanpage mà tài khoản đang quản lý trên Facebook"""
        if not self.page:
            self.start()

        pages = []
        try:
            self.page.goto("https://www.facebook.com/pages/?category=your_pages", timeout=35000)
            time.sleep(4)

            # Lấy danh sách thẻ link đại diện cho các Fanpage của bạn
            links = self.page.locator('div[role="main"] a[role="link"]').all()
            found_names = set()
            for l in links:
                href = l.get_attribute("href") or ""
                text = l.inner_text().strip()
                if "/" in href and len(text) > 1 and text not in ["Trang chủ", "Home", "Video", "Nhóm", "Groups"]:
                    lines = [line.strip() for line in text.split("\n") if line.strip()]
                    if lines and lines[0] not in found_names and len(lines[0]) < 60:
                        page_name = lines[0]
                        found_names.add(page_name)
                        clean_url = href.split("?")[0]
                        if not clean_url.startswith("http"):
                            clean_url = "https://www.facebook.com" + clean_url
                        pages.append({"name": page_name, "url": clean_url})
        except Exception as e:
            print("Lỗi quét Fanpage:", str(e))
        return pages

    def scan_group_posts(self, group_url, max_posts=6):
        """Quét các bài viết mới nhất trong Hội Nhóm Facebook (Group)"""
        if not self.page:
            self.start()

        posts = []
        try:
            self.page.goto(group_url, timeout=45000)
            time.sleep(4)

            for _ in range(3):
                self.page.evaluate("window.scrollBy(0, 700)")
                time.sleep(random.uniform(1.8, 2.8))

            articles = self.page.locator('div[role="feed"] > div, div[role="article"]').all()
            for article in articles:
                if len(posts) >= max_posts:
                    break

                text = article.inner_text().strip()
                if len(text) < 25:
                    continue

                lines = [l.strip() for l in text.split("\n") if l.strip()]
                filtered_lines = [l for l in lines if l not in ["Thích", "Bình luận", "Chia sẻ", "Gửi", "Like", "Comment", "Share"]]
                clean_text = " ".join(filtered_lines[:10])

                post_url = ""
                links = article.locator("a").all()
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "/posts/" in href or "/permalink/" in href:
                        post_url = href.split("?")[0]
                        if not post_url.startswith("http"):
                            post_url = "https://www.facebook.com" + post_url
                        break

                if not post_url:
                    post_url = f"{group_url}#post_{abs(hash(clean_text[:60]))}"

                if not is_post_already_commented(post_url):
                    posts.append({
                        "url": post_url,
                        "content": clean_text[:400],
                        "source": "Group"
                    })
        except Exception as e:
            print("Lỗi quét Group:", str(e))
        return posts

