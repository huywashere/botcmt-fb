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

    def __init__(self, headless=False, proxy=None):
        self.headless = headless
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

        proxy_config = None
        if self.proxy and self.proxy.strip():
            proxy_config = {"server": self.proxy.strip()}

        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=DATA_DIR,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            proxy=proxy_config,
            args=args
        )

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
        """Mở trình duyệt trực quan để người dùng tự đăng nhập và vượt 2FA"""
        self.headless = False
        self.start()
        self.page.goto("https://www.facebook.com", timeout=60000)
        # Giữ trình duyệt mở cho người dùng thao tác
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

                if not is_post_already_commented(post_url):
                    posts.append({
                        "url": post_url,
                        "content": clean_text[:400],
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

    def extract_single_post_content(self, post_url):
        """Mở 1 link bài viết cụ thể và trích xuất nội dung bài viết"""
        if not self.page:
            self.start()

        try:
            self.page.goto(post_url, timeout=45000)
            time.sleep(random.uniform(3, 5))

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
                        return text[:500]

            # Fallback lấy text trên body
            body_text = self.page.locator('body').inner_text()
            return body_text[:300]
        except Exception as e:
            return f"Không thể lấy nội dung bài viết: {str(e)}"

    def switch_to_fanpage(self, page_name=""):
        """Hỗ trợ chuyển đổi sang Profile Fanpage (New Page Experience)"""
        if not self.page:
            self.start()

        try:
            self.page.goto("https://www.facebook.com", timeout=30000)
            time.sleep(3)

            # Click vào Avatar menu góc trên bên phải
            avatar_btn = self.page.locator('div[aria-label*="Tài khoản của bạn"], div[aria-label*="Your profile"], svg[aria-label*="Tài khoản của bạn"]').first
            if avatar_btn.count() > 0:
                avatar_btn.click()
                time.sleep(2)

                # Tìm nút "Xem tất cả trang cá nhân" hoặc click vào Page nếu có tên
                see_all = self.page.locator('div[role="button"]:has-text("Xem tất cả trang cá nhân"), div[role="button"]:has-text("See all profiles")').first
                if see_all.count() > 0:
                    see_all.click()
                    time.sleep(2)

                if page_name:
                    target_page = self.page.locator(f'div[role="button"]:has-text("{page_name}")').first
                    if target_page.count() > 0:
                        target_page.click()
                        time.sleep(4)
                        return True, f"Đã chuyển sang Fanpage: {page_name}"
            return True, "Giữ nguyên profile hiện tại"
        except Exception as e:
            return False, f"Không thể tự động switch page: {str(e)}"

