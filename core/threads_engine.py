import os
import sys
import time
import random
import urllib.parse
from playwright.sync_api import sync_playwright
from core.db import get_setting, log_threads_comment, is_threads_post_already_commented
from core.ai_engine import is_vietnamese_text, is_blocked_post

THREADS_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "threads_user_data")
os.makedirs(THREADS_DATA_DIR, exist_ok=True)
BASE_URL = "https://www.threads.com"

class ThreadsEngine:
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
        """Kiểm tra tức thì (5ms) cookie sessionid trong User Data mà không cần mở trình duyệt"""
        candidates = [
            os.path.join(THREADS_DATA_DIR, "Default", "Network", "Cookies"),
            os.path.join(THREADS_DATA_DIR, "Default", "Cookies")
        ]
        for p in candidates:
            if os.path.exists(p):
                try:
                    import sqlite3
                    clean_path = p.replace('\\', '/')
                    conn = sqlite3.connect(f"file:{clean_path}?immutable=1", uri=True)
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM cookies WHERE (host_key LIKE '%threads.com%' OR host_key LIKE '%instagram.com%') AND name = 'sessionid'")
                    cnt = cur.fetchone()[0]
                    conn.close()
                    if cnt > 0:
                        return True
                except Exception:
                    pass
        return False

    @staticmethod
    def close_conflicting_chrome():
        """Đóng các tiến trình Chrome thủ công đang dùng thư mục threads_user_data để tránh xung đột SingletonLock"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (proc.info.get('name') or '').lower()
                    cmdline = " ".join(proc.info.get('cmdline') or [])
                    if 'chrome' in name and 'threads_user_data' in cmdline:
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
        """Khởi động trình duyệt Playwright với User Data riêng biệt cho Threads"""
        if self.page:
            return self.page

        if ThreadsEngine._active_instance and ThreadsEngine._active_instance != self:
            try:
                ThreadsEngine._active_instance.close()
            except Exception:
                pass

        # Xóa lock file nếu còn sót lại
        lock_file = os.path.join(THREADS_DATA_DIR, "SingletonLock")
        if os.path.exists(lock_file):
            ThreadsEngine.close_conflicting_chrome()
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

        proxy_config = ThreadsEngine.parse_proxy(self.proxy)
        chrome_path = ThreadsEngine.get_system_chrome_path()
        channel = "chrome" if chrome_path else None

        launch_kwargs = {
            "user_data_dir": THREADS_DATA_DIR,
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
                ThreadsEngine.close_conflicting_chrome()
                time.sleep(2.0)

        ThreadsEngine._active_instance = self

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
        """Đóng an toàn trình duyệt Threads"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass
        finally:
            if ThreadsEngine._active_instance == self:
                ThreadsEngine._active_instance = None
            self.context = None
            self.playwright = None
            self.page = None

    def open_for_login(self):
        """Mở cửa sổ Chrome thật để người dùng tự do đăng nhập Threads và ghi nhớ phiên vĩnh viễn"""
        self.close()
        # Xóa SingletonLock cũ nếu có
        lock_file = os.path.join(THREADS_DATA_DIR, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except Exception:
                pass

        chrome_path = ThreadsEngine.get_system_chrome_path()
        if chrome_path:
            import subprocess
            subprocess.Popen([
                chrome_path,
                f"--user-data-dir={THREADS_DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                f"{BASE_URL}/"
            ])
            return True
        else:
            self.headless = False
            self.start()
            self.page.goto(f"{BASE_URL}/", timeout=60000)
            return True

    def check_is_logged_in(self):
        """Kiểm tra xem tài khoản Threads đã được đăng nhập chưa"""
        # Kiểm tra cookie trước tiên (nhanh 5ms không cần đợi mạng)
        if ThreadsEngine.check_cookie_login():
            return True

        self.start()
        try:
            self.page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=15000)
            time.sleep(2.5)

            current_url = self.page.url.lower()
            if "login" in current_url:
                return False

            # Kiểm tra modal ép đăng nhập
            dialogs = self.page.query_selector_all('div[role="dialog"]')
            for d in dialogs:
                txt = d.inner_text().lower()
                if "tiếp tục bằng instagram" in txt or "continue with instagram" in txt or "sign up to chime in" in txt:
                    return False

            # Kiểm tra nút Đăng nhập hiển thị
            login_btns = self.page.query_selector_all('button:has-text("Đăng nhập"), button:has-text("Log in"), a[href*="/login"]')
            for btn in login_btns:
                if btn.is_visible():
                    return False

            # Kiểm tra các dấu hiệu đăng nhập thành công
            body_text = self.page.inner_text("body").lower()
            if "có gì mới?" in body_text or "có gì mới" in body_text or "what's new" in body_text or "dành cho bạn" in body_text:
                return True

            # Kiểm tra icon Profile / Nav
            nav_profile = self.page.query_selector('a[href*="/@"][role="link"], svg[aria-label*="Profile"], svg[aria-label*="cá nhân"], [aria-label="Tạo bài viết mới"], [aria-label="Create thread"]')
            if nav_profile:
                return True

            # Kiểm tra nút Post/Đăng trên home feed
            post_btn = self.page.query_selector('div[role="button"]:has-text("Post"), button:has-text("Post"), div[role="button"]:has-text("Đăng"), button:has-text("Đăng")')
            if post_btn:
                return True

            return False
        except Exception as e:
            print("Lỗi kiểm tra trạng thái login Threads:", str(e))
            return False

    def scan_movie_threads(self, keywords=None, max_posts=10):
        """
        Tự động tìm kiếm các bài thảo luận về phim ảnh trên Threads.
        Sử dụng cơ chế cào thông minh theo từ khóa phim ảnh.
        Nếu không có bài phim nào -> Tự động cào bài viết thường văn bản.
        """
        self.start()

        if not keywords:
            raw_kw = get_setting("threads_keywords", "phim, review phim, web phim, phim hay, netflix, phim rạp, cày phim, mọt phim, phim bộ")
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

            search_url = f"{BASE_URL}/search?q={urllib.parse.quote(kw)}&serp_type=default"
            try:
                self.page.goto(search_url, wait_until="domcontentloaded", timeout=18000)
                time.sleep(random.uniform(2.5, 3.5))

                # Lướt nhẹ 2 lần để tải thêm bài thảo luận mới
                for _ in range(2):
                    self.page.mouse.wheel(0, random.randint(600, 1000))
                    time.sleep(random.uniform(1.5, 2.0))

                # Tìm tất cả link bài viết Threads dạng /@username/post/post_id
                links = self.page.query_selector_all('a[href*="/post/"]')
                for link in links:
                    if len(scanned_results) >= max_posts:
                        break

                    href = link.get_attribute("href")
                    if not href:
                        continue

                    # Làm sạch URL bỏ param và media subpath, chuyển thành URL chuẩn threads.com
                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    clean_url = full_url.split("?")[0].replace("/media", "").replace("threads.net", "threads.com")

                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)

                    # Bỏ qua nếu bài này đã từng cmt thành công trước đó
                    if is_threads_post_already_commented(clean_url):
                        continue

                    # Trích xuất nội dung thảo luận bài viết
                    snippet = ""
                    author = ""
                    try:
                        container = link.evaluate_handle("""el => {
                            return el.closest("div[data-pressable-container='true']") || 
                                   el.closest("article") || 
                                   el.closest("div[tabindex='-1']") || 
                                   el.parentElement.parentElement.parentElement;
                        }""")
                        if container:
                            raw_text = container.inner_text().strip()
                            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                            if lines:
                                author = lines[0]
                                content_lines = [l for l in lines[1:] if l not in ["Like", "Comment", "Repost", "Share", "Thích", "Bình luận", "Chia sẻ"]]
                                snippet = " ".join(content_lines)
                    except Exception:
                        pass

                    if not snippet:
                        snippet = link.inner_text().strip()

                    snippet_clean = snippet.replace("\n", " ").strip()
                    if len(snippet_clean) < 15:
                        continue

                    # Trích xuất username từ URL nếu chưa có author
                    if not author:
                        import re
                        m_th = re.search(r'/@([^/?]+)', clean_url)
                        if m_th:
                            author = m_th.group(1)

                    # Né các trang/kênh bị chặn (như chợ phim, tô phim, sofaflix...)
                    if is_blocked_post(author=author, url=clean_url, content=snippet_clean):
                        print(f"[Threads] Bỏ qua bài từ trang né cmt: {author} ({clean_url})")
                        continue

                    # Lọc nghiêm ngặt: Chỉ lấy bài viết tiếng Việt của người Việt Nam
                    if not is_vietnamese_text(snippet_clean):
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
                print(f"Lỗi quét Threads với từ khóa '{kw}':", str(e))
                continue

        # NẾU KHÔNG CÓ BÀI THẢO LUẬN PHIM NÀO HOẶC ĐÃ BÌNH LUẬN HẾT:
        # Tự động chuyển sang cào các bài viết thường văn bản trên bảng tin Threads
        if len(scanned_results) == 0 and get_setting("fallback_to_general_posts", "1") == "1":
            print("[Threads] Không tìm thấy bài phim mới trong tìm kiếm. Tự động chuyển sang cào bảng tin bài viết thường...")
            try:
                self.page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=18000)
                time.sleep(random.uniform(2.5, 3.5))

                for _ in range(3):
                    self.page.mouse.wheel(0, random.randint(500, 900))
                    time.sleep(random.uniform(1.2, 2.0))

                links = self.page.query_selector_all('a[href*="/post/"]')
                for link in links:
                    if len(scanned_results) >= max_posts:
                        break

                    href = link.get_attribute("href")
                    if not href:
                        continue

                    full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    clean_url = full_url.split("?")[0].replace("/media", "").replace("threads.net", "threads.com")

                    if clean_url in seen_urls or is_threads_post_already_commented(clean_url):
                        continue
                    seen_urls.add(clean_url)

                    snippet = ""
                    author = ""
                    try:
                        container = link.evaluate_handle("""el => {
                            return el.closest("div[data-pressable-container='true']") || 
                                   el.closest("article") || 
                                   el.closest("div[tabindex='-1']") || 
                                   el.parentElement.parentElement.parentElement;
                        }""")
                        if container:
                            raw_text = container.inner_text().strip()
                            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                            if lines:
                                author = lines[0]
                                content_lines = [l for l in lines[1:] if l not in ["Like", "Comment", "Repost", "Share", "Thích", "Bình luận", "Chia sẻ"]]
                                snippet = " ".join(content_lines)
                    except Exception:
                        pass

                    if not snippet:
                        snippet = link.inner_text().strip()

                    snippet_clean = snippet.replace("\n", " ").strip()
                    if len(snippet_clean) < 15:
                        continue

                    # Trích xuất username từ URL nếu chưa có author
                    if not author:
                        import re
                        m_th = re.search(r'/@([^/?]+)', clean_url)
                        if m_th:
                            author = m_th.group(1)

                    # Né các trang/kênh bị chặn (như chợ phim, tô phim, sofaflix...)
                    if is_blocked_post(author=author, url=clean_url, content=snippet_clean):
                        print(f"[Threads] Bỏ qua bài từ trang né cmt: {author} ({clean_url})")
                        continue

                    # Lọc nghiêm ngặt: Chỉ lấy bài viết tiếng Việt của người Việt Nam
                    if not is_vietnamese_text(snippet_clean):
                        continue

                    if any(bad in snippet_clean.lower() for bad in blacklist):
                        continue

                    scanned_results.append({
                        "url": clean_url,
                        "content": snippet_clean[:280],
                        "author": author[:50],
                        "keyword": "Bài viết thường (Tự động chuyển)",
                        "is_general_post": True
                    })
            except Exception as e:
                print("[Threads] Lỗi cào bảng tin bài viết thường:", str(e))

        return scanned_results

    def comment_on_thread(self, post_url, comment_text):
        """
        Điều hướng tới bài viết Threads và thực hiện bình luận thông minh.
        """
        # Kiểm tra trước khi mở trình duyệt
        if is_blocked_post(url=post_url):
            print(f"[Threads] Bỏ qua cmt: URL thuộc trang né cmt: {post_url}")
            return False, "Trang thuộc danh sách chặn né bình luận (chợ phim, tô phim, sofaflix...)"

        self.start()
        try:
            # Đảm bảo dùng domain chuẩn threads.com
            post_url = post_url.replace("threads.net", "threads.com")
            print(f"[Threads] Đang mở bài viết: {post_url}")
            self.page.goto(post_url, wait_until="domcontentloaded", timeout=18000)
            time.sleep(random.uniform(2.5, 3.5))

            # Kiểm tra bài viết bị xóa hoặc 404
            page_text = self.page.inner_text("body")
            if "Không phải cứ biến mất là mất tích" in page_text or "This page isn't available" in page_text:
                return False, "Bài viết Threads không tồn tại hoặc đã bị xóa."

            # Kiểm tra an toàn sau khi tải trang thực tế
            current_url = self.page.url
            if is_blocked_post(url=current_url, content=page_text[:600]):
                print(f"[Threads] Phát hiện trang thuộc danh sách né cmt: {current_url}")
                return False, "Trang thuộc danh sách chặn né bình luận (chợ phim, tô phim, sofaflix...)"

            # Tự động thả Tim (Like) bài viết Threads trước khi bình luận
            if get_setting("auto_like_enabled", "1") == "1":
                try:
                    like_btn = self.page.query_selector('svg[aria-label="Thích"], svg[aria-label="Like"], div[role="button"][aria-label*="Thích"], div[role="button"][aria-label*="Like"]')
                    if like_btn:
                        like_btn.click()
                        time.sleep(random.uniform(0.8, 1.5))
                except Exception:
                    pass

            # 1. Tìm nút 'Mở rộng công cụ soạn' (Expand composer) hoặc click vào ô soạn thảo inline
            expand_btn = self.page.query_selector('div[role="button"][aria-label*="Mở rộng"], div[role="button"][aria-label*="Expand"]')
            if not expand_btn:
                inline_tb = self.page.query_selector('div[data-lexical-editor="true"][role="textbox"], div[role="textbox"]')
                if inline_tb:
                    try:
                        inline_tb.click()
                        time.sleep(1)
                    except Exception:
                        pass
                expand_btn = self.page.query_selector('div[role="button"][aria-label*="Mở rộng"], div[role="button"][aria-label*="Expand"]')

            if expand_btn:
                try:
                    expand_btn.click()
                except Exception:
                    expand_btn.evaluate('el => el.click()')
                time.sleep(1.5)

            # 2. Tìm khung soạn thảo (trong Modal dialog hoặc trên trang)
            dialog = self.page.query_selector('div[role="dialog"]')
            target_container = dialog if dialog else self.page

            input_box = target_container.query_selector('div[data-lexical-editor="true"][role="textbox"], div[role="textbox"], div[contenteditable="true"]')
            if not input_box:
                return False, "Không tìm thấy ô nhập bình luận trên bài viết Threads."

            # Focus và nhập bình luận mô phỏng gõ phím người thật
            input_box.click(force=True)
            time.sleep(0.5)

            try:
                self.page.keyboard.type(comment_text, delay=random.randint(18, 32))
            except Exception:
                input_box.fill(comment_text)

            time.sleep(random.uniform(1.2, 2.0))

            # 3. Tìm nút Đăng / Post
            post_btn = target_container.query_selector('div[role="button"]:has-text("Đăng"), div[role="button"]:has-text("Post"), button:has-text("Đăng"), button:has-text("Post")')
            
            if post_btn:
                aria_dis = post_btn.get_attribute("aria-disabled")
                if aria_dis == "true":
                    time.sleep(1.0)
                try:
                    post_btn.click(timeout=5000)
                except Exception:
                    post_btn.evaluate('el => el.click()')
            else:
                self.page.keyboard.press("Control+Enter")

            time.sleep(random.uniform(3.0, 4.5))

            print(f"[Threads] Đã gửi bình luận thành công cho bài: {post_url}")
            return True, "Đã gửi bình luận Threads thành công"

        except Exception as e:
            err_msg = str(e)
            print(f"[Threads] Lỗi gửi bình luận: {err_msg}")
            return False, err_msg
