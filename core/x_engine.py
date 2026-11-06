import os
import sys
import time
import random
import urllib.parse
from playwright.sync_api import sync_playwright
from core.db import get_setting, log_x_comment, is_x_post_already_commented
from core.ai_engine import is_vietnamese_text, is_blocked_post, is_movie_related

X_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "x_user_data")
os.makedirs(X_DATA_DIR, exist_ok=True)
BASE_URL = "https://x.com"

class XEngine:
    _active_instance = None

    def __init__(self, headless=True, proxy=None):
        self.headless = headless
        self.proxy = proxy or get_setting("proxy_string", "")
        self.playwright = None
        self.context = None
        self.page = None

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
    def check_cookie_login():
        """Kiểm tra tức thì (5ms) cookie auth_token hoặc twid của X (Twitter) trong User Data"""
        candidates = [
            os.path.join(X_DATA_DIR, "Default", "Network", "Cookies"),
            os.path.join(X_DATA_DIR, "Default", "Cookies")
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    import sqlite3
                    clean_path = p.replace('\\', '/')
                    conn = sqlite3.connect(f"file:{clean_path}?immutable=1", uri=True)
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT count(*) FROM cookies 
                        WHERE (host_key LIKE '%x.com%' OR host_key LIKE '%twitter.com%') 
                        AND name IN ('auth_token', 'twid')
                    """)
                    cnt = cur.fetchone()[0]
                    conn.close()
                    if cnt > 0:
                        return True
                except Exception:
                    pass
        return False

    @staticmethod
    def close_conflicting_chrome():
        """Đóng các tiến trình Chrome thủ công đang dùng thư mục x_user_data để tránh xung đột SingletonLock"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    cmdline = " ".join(proc.info.get('cmdline') or [])
                    if 'chrome' in name and 'x_user_data' in cmdline:
                        proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            time.sleep(1.5)
        except Exception:
            pass

    @staticmethod
    def parse_proxy(proxy_str):
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

    def start(self):
        """Khởi động trình duyệt Playwright với User Data riêng biệt cho X (Twitter)"""
        if self.page:
            return self.page

        if XEngine._active_instance and XEngine._active_instance != self:
            try:
                XEngine._active_instance.close()
            except Exception:
                pass

        # Xóa lock file nếu còn sót lại
        lock_file = os.path.join(X_DATA_DIR, "SingletonLock")
        if os.path.exists(lock_file):
            XEngine.close_conflicting_chrome()
            try:
                os.remove(lock_file)
            except Exception:
                pass

        self.playwright = sync_playwright().start()

        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--lang=vi-VN,vi,en-US,en"
        ]

        proxy_config = XEngine.parse_proxy(self.proxy)
        chrome_path = XEngine.get_system_chrome_path()
        channel = "chrome" if chrome_path else None

        launch_kwargs = {
            "user_data_dir": X_DATA_DIR,
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "locale": "vi-VN",
            "timezone_id": "Asia/Ho_Chi_Minh",
            "proxy": proxy_config,
            "ignore_default_args": ["--enable-automation"],
            "args": args
        }
        if channel:
            launch_kwargs["channel"] = channel

        # Thử mở trình duyệt (tự động thử lại 3 lần nếu có độ trễ giải phóng file lock)
        for attempt in range(3):
            try:
                self.context = self.playwright.chromium.launch_persistent_context(**launch_kwargs)
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                XEngine.close_conflicting_chrome()
                time.sleep(2.0)

        XEngine._active_instance = self

        if len(self.context.pages) > 0:
            self.page = self.context.pages[0]
            for p in self.context.pages[1:]:
                try:
                    p.close()
                except Exception:
                    pass
        else:
            self.page = self.context.new_page()

        # Stealth evasion
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        return self.page

    def close(self):
        """Đóng an toàn trình duyệt X"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            if XEngine._active_instance == self:
                XEngine._active_instance = None
            self.context = None
            self.playwright = None
            self.page = None

    def open_for_login(self):
        """Mở cửa sổ Chrome thật để người dùng tự do đăng nhập X (Twitter) và ghi nhớ phiên vĩnh viễn"""
        self.close()
        lock_file = os.path.join(X_DATA_DIR, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except Exception:
                pass

        chrome_path = XEngine.get_system_chrome_path()
        if chrome_path:
            import subprocess
            subprocess.Popen([
                chrome_path,
                f"--user-data-dir={X_DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                f"{BASE_URL}/login"
            ])
            return True
        else:
            self.headless = False
            self.start()
            self.page.goto(f"{BASE_URL}/login", timeout=60000)
            return True

    def check_is_logged_in(self):
        """Kiểm tra xem tài khoản X đã được đăng nhập chưa"""
        # Kiểm tra cookie trước tiên (nhanh 5ms không cần đợi mạng)
        if XEngine.check_cookie_login():
            return True

        self.start()
        try:
            self.page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2.5)

            current_url = self.page.url.lower()
            if "login" in current_url or "i/flow" in current_url:
                return False

            # Kiểm tra các dấu hiệu đăng nhập thành công của X
            # Nút tạo tweet / Profile icon / Nav / Textarea
            has_nav = self.page.query_selector('[data-testid="SideNav_NewTweet_Button"], [data-testid="AppTabBar_Profile_Link"], [data-testid="tweetTextarea_0"], nav[role="navigation"] a[href*="/home"]')
            if has_nav:
                return True

            body_text = self.page.inner_text("body").lower()
            if "dành cho bạn" in body_text or "for you" in body_text or "đang theo dõi" in body_text:
                return True

            return False
        except Exception as e:
            print("Lỗi kiểm tra trạng thái login X:", str(e))
            return False

    def scan_movie_tweets(self, keywords=None, max_posts=10):
        """
        Tự động tìm kiếm các bài thảo luận về phim ảnh trên X (Twitter).
        Sử dụng cơ chế cào thông minh theo từ khóa phim ảnh.
        Nếu không có bài phim nào -> Tự động cào tweet thường văn bản.
        """
        self.start()

        if not keywords:
            raw_kw = get_setting("x_keywords", "phim, review phim, web phim, phim hay, netflix, phim rạp, cày phim, mọt phim, phim bộ")
            keywords = [k.strip() for k in raw_kw.split(",") if k.strip()]

        if not keywords:
            keywords = ["phim", "review phim", "web phim", "phim hay"]

        # Chọn 1-2 từ khóa ngẫu nhiên trong mỗi đợt quét để đa dạng hóa
        chosen_keywords = random.sample(keywords, min(len(keywords), 2))
        scanned_results = []
        seen_urls = set()

        blacklist_raw = get_setting("blacklist_keywords", "tuyển dụng, bán hàng, giá rẻ, vay tiền, scam, lừa đảo, cờ bạc")
        blacklist = [b.strip().lower() for b in blacklist_raw.split(",") if b.strip()]

        for kw in chosen_keywords:
            if len(scanned_results) >= max_posts:
                break

            # Đảm bảo 100% kết quả từ cộng đồng người Việt Nam trên X
            search_query = kw if "lang:" in kw else f"{kw} lang:vi"
            search_url = f"{BASE_URL}/search?q={urllib.parse.quote(search_query)}&f=live"
            try:
                self.page.goto(search_url, wait_until="domcontentloaded", timeout=18000)
                time.sleep(random.uniform(2.5, 3.5))

                # Lướt nhẹ 2 lần để tải thêm tweet mới
                for _ in range(2):
                    self.page.mouse.wheel(0, random.randint(600, 1000))
                    time.sleep(random.uniform(1.5, 2.0))

                # Tìm tất cả tweet trên X
                tweet_elements = self.page.query_selector_all('article[data-testid="tweet"]')
                for article in tweet_elements:
                    if len(scanned_results) >= max_posts:
                        break

                    # Tìm link tweet permalink /username/status/id
                    status_link = article.query_selector('a[href*="/status/"]')
                    if not status_link:
                        continue

                    href = status_link.get_attribute("href")
                    if not href:
                        continue

                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    clean_url = full_url.split("?")[0].replace("twitter.com", "x.com")

                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)

                    # Bỏ qua nếu tweet này đã từng cmt thành công trước đó
                    if is_x_post_already_commented(clean_url):
                        continue

                    # Trích xuất tác giả và nội dung
                    author = ""
                    try:
                        author_el = article.query_selector('div[data-testid="User-Name"]')
                        if author_el:
                            author = author_el.inner_text().split("\n")[0].strip()
                    except Exception:
                        pass

                    snippet = ""
                    try:
                        text_el = article.query_selector('div[data-testid="tweetText"]')
                        if text_el:
                            snippet = text_el.inner_text().strip()
                    except Exception:
                        pass

                    if not snippet:
                        snippet = article.inner_text().strip()

                    snippet_clean = snippet.replace("\n", " ").strip()
                    if len(snippet_clean) < 15:
                        continue

                    # Trích xuất handle từ URL nếu chưa có author
                    if not author:
                        import re
                        m_x = re.search(r'(?:x|twitter)\.com/([^/?]+)/status/', clean_url)
                        if m_x:
                            author = m_x.group(1)

                    # Né các trang/kênh bị chặn (như chợ phim, tô phim, sofaflix...)
                    if is_blocked_post(author=author, url=clean_url, content=snippet_clean):
                        print(f"[X] Bỏ qua tweet từ trang né cmt: {author} ({clean_url})")
                        continue

                    # Lọc nghiêm ngặt: Chỉ lấy bài viết tiếng Việt của người Việt Nam
                    if not is_vietnamese_text(snippet_clean):
                        continue

                    # BẮT BUỘC: Tweet phải chung chủ đề hoặc liên quan tới phim ảnh (dù liên quan nhẹ)
                    if not is_movie_related(snippet_clean, keywords):
                        continue

                    # Lọc từ khóa cấm / blacklist
                    snippet_lower = snippet_clean.lower()
                    if any(bad in snippet_lower for bad in blacklist):
                        continue

                    scanned_results.append({
                        "url": clean_url,
                        "content": snippet_clean[:280],
                        "author": author[:50],
                        "keyword": kw,
                        "is_general_post": False
                    })

            except Exception as e:
                print(f"Lỗi quét 𝕏 với từ khóa '{kw}':", str(e))
                continue

        # NẾU KHÔNG CÓ TWEET PHIM NÀO HOẶC ĐÃ BÌNH LUẬN HẾT:
        # Tự động chuyển sang cào các tweet thường văn bản trên bảng tin Trang chủ X
        if len(scanned_results) == 0 and get_setting("fallback_to_general_posts", "1") == "1":
            print("[X] Không tìm thấy tweet phim mới trong tìm kiếm. Tự động chuyển sang cào bảng tin tweet thường...")
            try:
                self.page.goto(f"{BASE_URL}/home", wait_until="domcontentloaded", timeout=18000)
                time.sleep(random.uniform(2.5, 3.5))

                for _ in range(3):
                    self.page.mouse.wheel(0, random.randint(500, 900))
                    time.sleep(random.uniform(1.2, 2.0))

                tweet_elements = self.page.query_selector_all('article[data-testid="tweet"]')
                for article in tweet_elements:
                    if len(scanned_results) >= max_posts:
                        break

                    status_link = article.query_selector('a[href*="/status/"]')
                    if not status_link:
                        continue

                    href = status_link.get_attribute("href")
                    if not href:
                        continue

                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    clean_url = full_url.split("?")[0].replace("twitter.com", "x.com")

                    if clean_url in seen_urls or is_x_post_already_commented(clean_url):
                        continue
                    seen_urls.add(clean_url)

                    author = ""
                    try:
                        author_el = article.query_selector('div[data-testid="User-Name"]')
                        if author_el:
                            author = author_el.inner_text().split("\n")[0].strip()
                    except Exception:
                        pass

                    snippet = ""
                    try:
                        text_el = article.query_selector('div[data-testid="tweetText"]')
                        if text_el:
                            snippet = text_el.inner_text().strip()
                    except Exception:
                        pass

                    if not snippet:
                        snippet = article.inner_text().strip()

                    snippet_clean = snippet.replace("\n", " ").strip()
                    if len(snippet_clean) < 15:
                        continue

                    # Trích xuất handle từ URL nếu chưa có author
                    if not author:
                        import re
                        m_x = re.search(r'(?:x|twitter)\.com/([^/?]+)/status/', clean_url)
                        if m_x:
                            author = m_x.group(1)

                    # Né các trang/kênh bị chặn (như chợ phim, tô phim, sofaflix...)
                    if is_blocked_post(author=author, url=clean_url, content=snippet_clean):
                        print(f"[X] Bỏ qua tweet từ trang né cmt: {author} ({clean_url})")
                        continue

                    # Lọc nghiêm ngặt: Chỉ lấy bài viết tiếng Việt của người Việt Nam
                    if not is_vietnamese_text(snippet_clean):
                        continue

                    # BẮT BUỘC: Tweet phải chung chủ đề hoặc liên quan tới phim ảnh (dù liên quan nhẹ)
                    if not is_movie_related(snippet_clean, keywords):
                        continue

                    if any(bad in snippet_clean.lower() for bad in blacklist):
                        continue

                    scanned_results.append({
                        "url": clean_url,
                        "content": snippet_clean[:280],
                        "author": author[:50],
                        "keyword": "Tweet thường (Tự động chuyển)",
                        "is_general_post": True
                    })
            except Exception as e:
                print("[X] Lỗi cào bảng tin tweet thường:", str(e))

        return scanned_results

    def comment_on_tweet(self, tweet_url, comment_text):
        """
        Điều hướng tới Tweet X và thực hiện bình luận thông minh.
        """
        # Kiểm tra trước khi mở trình duyệt
        if is_blocked_post(url=tweet_url):
            print(f"[X] Bỏ qua cmt: URL thuộc trang né cmt: {tweet_url}")
            return False, "Trang thuộc danh sách chặn né bình luận (chợ phim, tô phim, sofaflix, mâm phim, vườn phim...)"

        self.start()
        try:
            tweet_url = tweet_url.replace("twitter.com", "x.com")
            print(f"[X] Đang mở Tweet: {tweet_url}")
            self.page.goto(tweet_url, wait_until="domcontentloaded", timeout=18000)
            time.sleep(random.uniform(2.5, 3.5))

            # Kiểm tra Tweet bị xóa hoặc 404
            page_text = self.page.inner_text("body")
            if "Hmm...this page doesn’t exist" in page_text or "This Tweet was deleted" in page_text or "Trang này không tồn tại" in page_text:
                return False, "Tweet trên 𝕏 không tồn tại hoặc đã bị xóa."

            # Kiểm tra an toàn sau khi tải trang thực tế
            current_url = self.page.url
            if is_blocked_post(url=current_url, content=page_text[:600]):
                print(f"[X] Phát hiện trang thuộc danh sách né cmt: {current_url}")
                return False, "Trang thuộc danh sách chặn né bình luận (chợ phim, tô phim, sofaflix, mâm phim, vườn phim...)"

            # Tự động thả Tim (Like) Tweet trước khi bình luận (Tạo thông báo kép kích thích tác giả tương tác)
            if get_setting("auto_like_enabled", "1") == "1":
                try:
                    like_btn = self.page.query_selector('article[data-testid="tweet"] button[data-testid="like"], button[data-testid="like"]')
                    if like_btn:
                        like_btn.click()
                        time.sleep(random.uniform(0.8, 1.5))
                except Exception:
                    pass

            # 1. Tìm ô soạn thảo trả lời (Reply textarea)
            # Thử click nút Reply nếu ô inline chưa mở
            input_box = self.page.query_selector('div[data-testid="tweetTextarea_0"]')
            if not input_box:
                reply_btn = self.page.query_selector('article[data-testid="tweet"] button[data-testid="reply"], article[data-testid="tweet"] div[data-testid="reply"]')
                if reply_btn:
                    try:
                        reply_btn.click()
                        time.sleep(1.5)
                    except Exception:
                        pass
                input_box = self.page.query_selector('div[data-testid="tweetTextarea_0"], div[role="textbox"][contenteditable="true"]')

            if not input_box:
                return False, "Không tìm thấy khung soạn thảo trả lời trên Tweet 𝕏."

            # Focus và gõ bình luận mô phỏng người thật
            input_box.click(force=True)
            time.sleep(0.5)

            try:
                self.page.keyboard.type(comment_text, delay=random.randint(18, 32))
            except Exception:
                input_box.fill(comment_text)

            time.sleep(random.uniform(1.2, 2.0))

            # 2. Tìm nút Đăng trả lời (Reply / Tweet button)
            post_btn = self.page.query_selector('button[data-testid="tweetButtonInline"], button[data-testid="tweetButton"], button:has-text("Reply"), button:has-text("Trả lời")')

            if post_btn:
                aria_dis = post_btn.get_attribute("aria-disabled")
                if aria_dis == "true":
                    time.sleep(1.0)
                try:
                    post_btn.click(timeout=5000)
                except Exception:
                    post_btn.evaluate('el => el.click()')
            else:
                # Phím tắt đăng bài trên X: Ctrl + Enter
                self.page.keyboard.press("Control+Enter")

            time.sleep(random.uniform(3.0, 4.5))

            print(f"[X] Đã gửi bình luận thành công cho Tweet: {tweet_url}")
            return True, "Đã gửi bình luận 𝕏 thành công"

        except Exception as e:
            err_msg = str(e)
            print(f"[X] Lỗi gửi bình luận: {err_msg}")
            return False, err_msg

