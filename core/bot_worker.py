import time
import random
import threading
from datetime import datetime
from core.db import (
    get_setting, set_setting, log_comment, 
    is_post_already_commented, get_recent_logs,
    get_pending_target_urls, mark_post_status,
    get_selected_fanpage
)
from core.ai_engine import AIEngine
from core.browser_engine import BrowserEngine
from core.telegram_notifier import TelegramNotifier

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
            self.notify_ui("status", "Đang quét bài viết ngầm...")
            browser = BrowserEngine(headless=True)
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

    def count_today_comments(self):
        """Đếm số bình luận đã gửi thành công trong ngày hôm nay"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        logs = get_recent_logs(limit=200)
        return sum(1 for l in logs if l.get("status") == "Đã gửi" and str(l.get("created_at", "")).startswith(today_str))

    def start_auto(self):
        """Bắt đầu chu trình tự động bình luận theo lịch"""
        if self.is_running:
            return

        self.is_running = True
        set_setting("auto_comment_enabled", "1")
        self.notify_ui("auto_state_changed", True)

        def _loop():
            self.browser = BrowserEngine(headless=True)
            self.notify_ui("status", "Hệ thống tự động bình luận đã khởi động ngầm...")
            
            session_start_time = time.time()
            consecutive_errors = 0

            # Cấu hình danh sách Fanpage xoay vòng
            fanpages_raw = get_setting("fanpage_rotation_list", "Flexphim").strip()
            fanpages = [fp.strip() for fp in fanpages_raw.split(",") if fp.strip()]
            current_page_idx = 0
            current_page_comments_count = 0
            rotate_threshold = int(get_setting("rotate_every_n_comments", "5"))

            # 1. TỰ ĐỘNG CHUYỂN ĐỔI SANG FANPAGE ĐẠI DIỆN TRƯỚC TIÊN (NGAY KHI MỞ)
            active_page = get_selected_fanpage() or (fanpages[0] if fanpages else "Flexphim")
            if active_page:
                self.notify_ui("status", f"Đang tự động chuyển đổi danh tính sang Fanpage '{active_page}'...")
                self.browser.switch_to_fanpage(active_page)

            # 2. Chế độ làm ấm session trên chính Fanpage (Warm-Up nhẹ 10s)
            if get_setting("warmup_enabled", "0") == "1":
                self.notify_ui("status", "Đang lướt nhẹ làm ấm session...")
                self.browser.run_warmup(duration_sec=10)

            while self.is_running:
                # 1. Kiểm tra hẹn giờ phiên chạy (Session Duration)
                duration_mins = int(get_setting("session_duration_minutes", "0"))
                if duration_mins > 0:
                    elapsed_mins = (time.time() - session_start_time) / 60
                    if elapsed_mins >= duration_mins:
                        msg = f"Đã hết thời hạn phiên chạy ({duration_mins} phút). Đã tự dừng an toàn!"
                        self.notify_ui("status", msg)
                        if get_setting("telegram_alerts_enabled", "0") == "1":
                            TelegramNotifier.send_message(f"⏹️ <b>[FB Bot]</b> {msg}")
                        break

                # 2. Kiểm tra giới hạn bình luận tối đa trong ngày (Daily Quota Protection)
                daily_limit = int(get_setting("daily_limit", "25"))
                today_count = self.count_today_comments()
                if today_count >= daily_limit:
                    msg = f"Đã đạt giới hạn an toàn {today_count}/{daily_limit} cmt hôm nay. Tự ngắt để bảo vệ Fanpage tuyệt đối!"
                    self.notify_ui("status", msg)
                    if get_setting("telegram_alerts_enabled", "0") == "1":
                        TelegramNotifier.send_message(f"🏆 <b>[FB Bot Hoàn Thành]</b> {msg}")
                    break

                # 3. Kiểm tra khung giờ cho phép (Active Hours)
                if not self.check_active_time():
                    self.notify_ui("status", "Đang ngoài khung giờ hoạt động (sau 23h hoặc trước 8h). Tạm nghỉ bảo vệ nick...")
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
                        data = self.browser.extract_single_post_content(target_url)
                        posts.append({
                            "url": target_url,
                            "content": data.get("content", ""),
                            "image_url": data.get("image_url", ""),
                            "source": "Custom URL"
                        })
                elif source_type == "groups":
                    group_url = get_setting("target_group_url", "").strip()
                    if group_url:
                        self.notify_ui("status", f"Đang quét bài viết mới trong Nhóm: {group_url[:35]}...")
                        posts = self.browser.scan_group_posts(group_url, max_posts=6)
                    else:
                        self.notify_ui("status", "Chưa nhập link Group Facebook mục tiêu. Tự động chuyển quét Newsfeed...")
                        posts = self.browser.scan_newsfeed_posts(max_posts=6)
                else:
                    self.notify_ui("status", "Đang quét bài viết mới trên Facebook...")
                    posts = self.browser.scan_newsfeed_posts(max_posts=6)

                # Lọc bài theo từ khóa nếu có cấu hình
                keywords_raw = get_setting("keywords", "").strip()
                keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]

                # Danh sách đen từ khóa loại trừ
                blacklist_raw = get_setting("blacklist_keywords", "").strip()
                blacklist = [b.strip().lower() for b in blacklist_raw.split(",") if b.strip()]

                max_age_hours = int(get_setting("max_post_age_hours", "24"))
                commented_this_round = 0

                for p in posts:
                    if not self.is_running:
                        break

                    post_content = p["content"]
                    post_url = p["url"]

                    # 1. Kiểm tra từ khóa loại trừ (Blacklist)
                    if blacklist and any(bad in post_content.lower() for bad in blacklist):
                        self.notify_ui("status", f"Bỏ qua bài do chứa từ khóa loại trừ: {post_url[:35]}...")
                        continue

                    # 2. Kiểm tra tuổi bài viết (Chỉ cmt bài dưới 24h)
                    if max_age_hours > 0:
                        first_snippet = post_content[:150].lower()
                        is_old = any(sig in first_snippet for sig in ["2 ngày", "3 ngày", "4 ngày", "5 ngày", "6 ngày", "1 tuần", "2 tuần", "1 tháng"])
                        if is_old:
                            self.notify_ui("status", f"Bỏ qua bài viết cũ quá 24h: {post_url[:35]}...")
                            continue

                    # 3. Kiểm tra từ khóa trọng tâm
                    if keywords:
                        has_kw = any(kw in post_content.lower() for kw in keywords)
                        if not has_kw:
                            self.notify_ui("status", f"Bỏ qua bài không chứa từ khóa phim: '{post_content[:35]}...'")
                            continue

                    if is_post_already_commented(post_url):
                        continue

                    # Xác định Fanpage đại diện đang active
                    current_fanpage_name = active_page or (fanpages[current_page_idx] if fanpages else "Flexphim")

                    # Sinh bình luận thông minh bằng Gemini Vision / Text / Spintax
                    self.notify_ui("status", f"AI đang phân tích ngữ cảnh & hình ảnh bài viết cho '{current_fanpage_name}'...")
                    comment_text = AIEngine.generate_comment(post_content, current_fanpage_name, image_url=p.get("image_url", ""))

                    # Gửi thông tin về UI
                    self.notify_ui("current_processing", {
                        "url": post_url,
                        "snippet": post_content,
                        "comment": comment_text,
                        "page": current_fanpage_name
                    })

                    # Chọn chế độ: Bình luận bài viết hoặc Trả lời bình luận
                    comment_mode = get_setting("comment_mode", "both")
                    self.notify_ui("status", f"Đang mô phỏng người thật tương tác vào bài: {post_url[:35]}...")
                    
                    if comment_mode == "reply":
                        success, msg = self.browser.reply_to_comment_on_post(post_url, comment_text)
                    elif comment_mode == "both":
                        if random.random() < 0.5:
                            success, msg = self.browser.reply_to_comment_on_post(post_url, comment_text)
                        else:
                            success, msg = self.browser.comment_on_post(post_url, comment_text)
                    else:
                        success, msg = self.browser.comment_on_post(post_url, comment_text)

                    status_str = "Đã gửi" if success else "Lỗi"
                    if success:
                        commented_this_round += 1
                    log_comment(post_url, post_content[:100], comment_text, current_fanpage_name, status_str, msg)
                    mark_post_status(post_url, "sent" if success else "failed")

                    # Gửi thông báo Telegram nếu được bật
                    if success and get_setting("telegram_alerts_enabled", "0") == "1":
                        TelegramNotifier.send_message(
                            f"🔔 <b>[FB Auto Comment]</b>\n"
                            f"🏷️ <b>Page</b>: {current_fanpage_name}\n"
                            f"🎬 <b>Bài viết</b>: {post_content[:65]}...\n"
                            f"💬 <b>Bình luận</b>: {comment_text}\n"
                            f"📊 <b>Tiến độ hôm nay</b>: {self.count_today_comments()}/{daily_limit}"
                        )

                    # Cơ chế ngắt khẩn cấp (Emergency Circuit Breaker)
                    if not success:
                        consecutive_errors += 1
                        if consecutive_errors >= 2:
                            warn_msg = "⚠️ CẢNH BÁO AN TOÀN: Gặp 2 lỗi liên tiếp từ Facebook. Hệ thống tự động DỪNG KHẨN CẤP để bảo vệ Fanpage chống checkpoint!"
                            self.notify_ui("status", warn_msg)
                            if get_setting("telegram_alerts_enabled", "0") == "1":
                                TelegramNotifier.send_message(f"🚨 <b>[CẢNH BÁO DỪNG BOT]</b>\n{warn_msg}")
                            self.stop()
                            break
                    else:
                        consecutive_errors = 0

                    self.notify_ui("comment_completed", {
                        "post_snippet": post_content[:80],
                        "comment_content": comment_text,
                        "status": status_str,
                        "time": datetime.now().strftime("%H:%M:%S")
                    })

                    # Kiểm tra xoay vòng Fanpage
                    if fanpages and len(fanpages) > 1 and success:
                        current_page_comments_count += 1
                        if current_page_comments_count >= rotate_threshold:
                            current_page_idx = (current_page_idx + 1) % len(fanpages)
                            next_page = fanpages[current_page_idx]
                            self.notify_ui("status", f"Đạt ngưỡng {rotate_threshold} cmt. Đang tự động đổi danh tính sang Fanpage: '{next_page}'...")
                            self.browser.switch_to_fanpage(next_page)
                            current_page_comments_count = 0

                    # Nghỉ ngẫu nhiên giữa 2 lần bình luận (~2 phút theo cấu hình)
                    min_d = int(get_setting("min_delay", "110"))
                    max_d = int(get_setting("max_delay", "130"))
                    delay_time = random.randint(min_d, max_d)

                    for sec in range(delay_time, 0, -1):
                        if not self.is_running:
                            break
                        mins = sec // 60
                        s = sec % 60
                        self.notify_ui("countdown", f"Chờ bài tiếp theo: {mins}p {s:02d}s")
                        time.sleep(1)

                # Sau khi hết lượt bài, chờ theo scan_interval (nếu không có bài mới chỉ chờ 15s để cuộn tiếp)
                scan_minutes = int(get_setting("scan_interval", "2"))
                wait_seconds = (scan_minutes * 60) if commented_this_round > 0 else 15
                if commented_this_round == 0:
                    self.notify_ui("status", "Đang cuộn sâu tìm các bài viết mới chưa từng bình luận...")
                else:
                    self.notify_ui("status", f"Đã bình luận xong lượt này ({commented_this_round} bài). Lần quét tiếp sau {scan_minutes} phút...")

                for sec in range(wait_seconds, 0, -1):
                    if not self.is_running:
                        break
                    mins = sec // 60
                    s = sec % 60
                    if mins > 0:
                        self.notify_ui("countdown", f"Lượt quét tiếp: {mins}p {s:02d}s")
                    else:
                        self.notify_ui("countdown", f"Lượt quét tiếp: {sec}s")
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

