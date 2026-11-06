import sqlite3
import os
import json
import csv
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot_database.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Auto-initialize database tables on first load
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Accounts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        fb_uid TEXT,
        status TEXT DEFAULT 'active',
        cookie_file TEXT,
        proxy TEXT DEFAULT '',
        last_login TIMESTAMP
    )
    """)

    # Fanpages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fanpages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        page_id TEXT,
        page_name TEXT NOT NULL,
        page_url TEXT,
        is_selected INTEGER DEFAULT 0,
        FOREIGN KEY (account_id) REFERENCES accounts (id)
    )
    """)

    # Scanned posts history (Newsfeed, Groups, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_url TEXT UNIQUE NOT NULL,
        author TEXT,
        content TEXT,
        source_type TEXT DEFAULT 'newsfeed',
        source_name TEXT,
        scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending'  -- 'pending', 'sent', 'skipped', 'failed'
    )
    """)

    # Comments history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comment_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_url TEXT NOT NULL,
        post_snippet TEXT,
        comment_content TEXT NOT NULL,
        page_name TEXT,
        status TEXT DEFAULT 'Đã gửi',  -- 'Đã gửi', 'Lỗi', 'Bỏ qua'
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Threads Comments history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS threads_comment_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_url TEXT NOT NULL,
        post_snippet TEXT,
        comment_content TEXT NOT NULL,
        status TEXT DEFAULT 'Đã gửi',  -- 'Đã gửi', 'Lỗi', 'Bỏ qua', 'Chưa gửi (Quét thử)'
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # X (Twitter) Comments history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS x_comment_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_url TEXT NOT NULL,
        post_snippet TEXT,
        comment_content TEXT NOT NULL,
        status TEXT DEFAULT 'Đã gửi',  -- 'Đã gửi', 'Lỗi', 'Bỏ qua', 'Chưa gửi (Quét thử)'
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Settings table (Key - Value)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Pre-populate default settings (Tối ưu chuyên sâu cho chủ đề Phim ảnh & Anti-ban)
    default_settings = {
        "gemini_api_key": "",
        "scan_interval": "2",       # 2 phút quét 1 lần
        "feed_source": "for_you",    # for_you, groups, custom_urls
        "min_delay": "110",          # Độ trễ tối thiểu an toàn (~2 phút)
        "max_delay": "130",          # Độ trễ tối đa an toàn (~2 phút)
        "fb_delay_preset": "2",      # Preset giãn cách cmt FB (1, 2, 3, 5 phút)
        "topic": "Phim ảnh, review phim, phim bộ Hàn/Trung/Âu Mỹ, chia sẻ cảm nhận điện ảnh, gợi ý phim hay",
        "persona": "Bạn trẻ Gen Z mê phim, cmt siêu ngắn gọn (8-15 từ), xưng tui bạn bè thân mật, dùng từ lóng giới trẻ (cuốn xỉu, nét căng, mượt đét, bao dính), rủ ghé web tui flexphim xem phim",
        "brand_mention": "web tui flexphim",
        "keywords": "phim, tập, diễn viên, mọt phim, xem ở đâu, review, netflix, bộ này, tên phim, chiếu rạp, sub, vietsub, thuyết minh, web phim",
        "spintax_samples": "{phim cuốn xỉu|mê bộ này ghê|cảnh này bao dính}, {ghé|qua} web tui flexphim xem phim {với tui nè|nha bạn ơi}!\n{tối rảnh|hôm nào rảnh} {ghé|qua|vô} web tui flexphim xem phim {xả stress|thư giãn} nha bạn ơi!\nbộ này {bên|trên} web tui flexphim có bản {nét căng|full hd} luôn á, {qua|ghé} cày thử nè!\ncoi trên web tui flexphim {mượt đét|bao mượt} luôn á bạn ơi, {ghé|qua} xem thử nè!\n{cuốn thực sự|đỉnh chóp luôn}, tối {qua|ghé} web tui flexphim cày trọn bộ {với tui nè|nha}!\nlên web tui flexphim xem phim {mượt mà không lo lag|bao phê} nè bạn ơi!",
        "auto_comment_enabled": "0",
        "daily_limit": "25",         # Giới hạn an toàn chống ban tuyệt đối: tối đa 25 cmt/ngày
        "active_start": "08:00",     # Chỉ chạy từ 8h sáng
        "active_end": "23:00",       # Dừng lúc 23h đêm (tránh FB quét bot đêm)
        "session_duration_minutes": "0",  # Hẹn giờ tắt: 0 = chạy theo khung giờ, 60 = chạy 1 tiếng tự tắt
        # Cấu hình tính năng mới mở rộng:
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "telegram_alerts_enabled": "0",
        "blacklist_keywords": "tuyển dụng, tuyển nv, bán hàng, giá rẻ, vay tiền, vay nhanh, scam, lừa đảo, cờ bạc, bóng đá, chính trị, chợ phim, tô phim, sofaflix",
        "blocked_authors": "chợ phim, to phim, tô phim, sofaflix, chophim, tophim, sofa flix",
        "max_post_age_hours": "24",  # Chỉ cmt bài đăng trong vòng 24h
        "comment_mode": "both",      # "post" (bình luận bài), "reply" (ưu tiên trả lời cmt người hỏi), "both"
        "fanpage_rotation_list": "Flex Phim",  # Danh sách tên các Fanpage cần xoay vòng (cách nhau bởi dấu phẩy)
        "rotate_every_n_comments": "5",       # Số cmt trước khi đổi sang Page tiếp theo
        "target_group_url": "",
        # 4 Vũ khí tối ưu đỉnh cao:
        "link_cloaking_enabled": "1",    # Tự động lách link chống Facebook Ghostban
        "gemini_vision_enabled": "1",    # Gemini Multimodal Vision đọc ảnh poster bài viết
        "warmup_enabled": "1",           # Làm ấm session 45s trước khi cmt
        "proxy_string": "",              # Cấu hình Proxy riêng (IP:Port:User:Pass)
        # Cấu hình riêng cho Threads Auto Bot:
        "threads_keywords": "phim, phim 18+, review phim, web phim, netflix, phim rạp, cày phim, mọt phim, phim bộ, phim người lớn, cảnh nóng, spoil phim, kdrama",
        "threads_scan_interval": "2",
        "threads_min_delay": "110",
        "threads_max_delay": "130",
        "threads_daily_limit": "50",
        "threads_auto_comment_enabled": "0",
        "threads_delay_preset": "2",     # Preset giãn cách cmt Threads (1, 2, 3, 5 phút)
        # Tự động chuyển bài viết thường văn bản khi không có bài phim:
        "fallback_to_general_posts": "1",
        # Thông báo Telegram riêng cho Threads:
        "threads_telegram_alerts_enabled": "1",
        # Cấu hình riêng cho X (Twitter) Auto Bot:
        "x_keywords": "phim, phim 18+, review phim, web phim, phim hay, netflix, phim rạp, cày phim, mọt phim, phim bộ, phim người lớn, cảnh nóng, spoil phim, trailer phim, chiếu rạp, kdrama, anime",
        "x_scan_interval": "2",
        "x_min_delay": "110",
        "x_max_delay": "130",
        "x_daily_limit": "100",
        "x_auto_comment_enabled": "0",
        "x_delay_preset": "2",           # Preset giãn cách cmt X (1, 2, 3, 5 phút)
        "x_telegram_alerts_enabled": "1"
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Đảm bảo có ít nhất Fanpage Flex Phim mặc định
    cursor.execute("SELECT COUNT(*) as cnt FROM fanpages")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("INSERT INTO fanpages (page_name, page_url, is_selected) VALUES ('Flex Phim', 'https://www.facebook.com', 1)")
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('selected_fanpage', 'Flex Phim')")

    conn.commit()
    conn.close()

def get_setting(key, default=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_all_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def log_comment(post_url, post_snippet, comment_content, page_name, status="Đã gửi", error=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO comment_logs (post_url, post_snippet, comment_content, page_name, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (post_url, post_snippet, comment_content, page_name, status, error))
    conn.commit()
    conn.close()

def get_recent_logs(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comment_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def export_logs_to_csv(filepath=None):
    """Xuất toàn bộ lịch sử bình luận ra file CSV tương thích tốt với Excel tiếng Việt"""
    if not filepath:
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lich_su_comment.csv")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM comment_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "URL Bài Viết", "Trích Đoạn Bài Gốc", "Nội Dung Bình Luận", "Tên Page", "Trạng Thái", "Lỗi", "Thời Gian"])
        for r in rows:
            writer.writerow([r["id"], r["post_url"], r["post_snippet"], r["comment_content"], r["page_name"], r["status"], r["error_message"], r["created_at"]])
    return filepath

def is_post_already_commented(post_url):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM comment_logs WHERE post_url = ? AND status = 'Đã gửi'", (post_url,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

# ==================== THREADS DATABASE HELPERS ====================
def log_threads_comment(post_url, post_snippet, comment_content, status="Đã gửi", error=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO threads_comment_logs (post_url, post_snippet, comment_content, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (post_url, post_snippet, comment_content, status, error))
    conn.commit()
    conn.close()

def get_recent_threads_logs(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM threads_comment_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def is_threads_post_already_commented(post_url):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM threads_comment_logs WHERE post_url = ? AND status = 'Đã gửi'", (post_url,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def export_threads_logs_to_csv(filepath=None):
    """Xuất toàn bộ lịch sử bình luận Threads ra file CSV"""
    if not filepath:
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lich_su_comment_threads.csv")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM threads_comment_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "URL Bài Threads", "Nội Dung Bài Threads", "Nội Dung Bình Luận", "Trạng Thái", "Lỗi", "Thời Gian"])
        for r in rows:
            writer.writerow([r["id"], r["post_url"], r["post_snippet"], r["comment_content"], r["status"], r["error_message"], r["created_at"]])
    return filepath

# ==================== X (TWITTER) DATABASE HELPERS ====================
def log_x_comment(post_url, post_snippet, comment_content, status="Đã gửi", error=""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO x_comment_logs (post_url, post_snippet, comment_content, status, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (post_url, post_snippet, comment_content, status, error))
    conn.commit()
    conn.close()

def get_recent_x_logs(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM x_comment_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def is_x_post_already_commented(post_url):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM x_comment_logs WHERE post_url = ? AND status = 'Đã gửi'", (post_url,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def export_x_logs_to_csv(filepath=None):
    """Xuất toàn bộ lịch sử bình luận X (Twitter) ra file CSV"""
    if not filepath:
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lich_su_comment_x.csv")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM x_comment_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    with open(filepath, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "URL Tweet X", "Nội Dung Tweet", "Nội Dung Bình Luận", "Trạng Thái", "Lỗi", "Thời Gian"])
        for r in rows:
            writer.writerow([r["id"], r["post_url"], r["post_snippet"], r["comment_content"], r["status"], r["error_message"], r["created_at"]])
    return filepath

def get_accounts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_target_url(url, source_name="Chỉ định"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO posts (post_url, content, source_type, source_name, status)
        VALUES (?, '', 'custom_urls', ?, 'pending')
    """, (url.strip(), source_name))
    conn.commit()
    conn.close()

def get_pending_target_urls(limit=20):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM posts 
        WHERE source_type = 'custom_urls' AND status = 'pending'
        ORDER BY id ASC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_post_status(post_url, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET status = ? WHERE post_url = ?", (status, post_url))
    conn.commit()
    conn.close()

def get_fanpages():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM fanpages")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_fanpage(page_name, page_url="", is_selected=0):
    """Lưu hoặc cập nhật Fanpage vào cơ sở dữ liệu"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM fanpages WHERE page_name = ?", (page_name.strip(),))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE fanpages SET page_url = ?, is_selected = ? WHERE id = ?", (page_url.strip(), is_selected, row["id"]))
    else:
        cursor.execute("""
            INSERT INTO fanpages (page_name, page_url, is_selected)
            VALUES (?, ?, ?)
        """, (page_name.strip(), page_url.strip(), is_selected))
    conn.commit()
    conn.close()

def set_selected_fanpage(page_name):
    """Đặt Fanpage được chọn làm đại diện bình luận"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE fanpages SET is_selected = 0")
    cursor.execute("UPDATE fanpages SET is_selected = 1 WHERE page_name = ?", (page_name.strip(),))
    conn.commit()
    conn.close()
    set_setting("selected_fanpage", page_name.strip())

def get_selected_fanpage():
    return get_setting("selected_fanpage", "Flex Phim")

# Luôn đảm bảo database và các bảng mặc định tồn tại khi import
init_db()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
