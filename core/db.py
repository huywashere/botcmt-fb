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
        "scan_interval": "5",       # 5 phút quét 1 lần
        "feed_source": "for_you",    # for_you, groups, custom_urls
        "min_delay": "150",          # Độ trễ tối thiểu an toàn (2.5 phút)
        "max_delay": "360",          # Độ trễ tối đa an toàn (6 phút)
        "topic": "Phim ảnh, review phim, phim bộ Hàn/Trung/Âu Mỹ, chia sẻ cảm nhận điện ảnh, gợi ý phim hay",
        "persona": "Một bạn trẻ mê phim chính hiệu (mọt phim), xưng tui/mình thân mật, chia sẻ chân thực, tự nhiên như người dùng mạng xã hội thực thụ (dùng các từ: nè, nha, coi cuốn, web mượt lắm...)",
        "brand_mention": "Vườn Phim => vuonphim chấm com",
        "keywords": "phim, tập, diễn viên, mọt phim, xem ở đâu, review, netflix, bộ này, tên phim, chiếu rạp, sub, vietsub, thuyết minh, web phim",
        "spintax_samples": "qua Vườn Phim thử đi nè, web bên tui làm á => vuonphim chấm com\nghé bên tui chơi thử xem sao nha, Vườn Phim nè => vuonphim chấm com\nbên tui là Vườn Phim nè, qua tìm thử phim bạn thích nha => vuonphim chấm com\nthử đổi gió qua Vườn Phim xem sao nè bạn ơi => vuonphim chấm com\ncoi bên Vườn Phim thử nha, nhà tui mới update á => vuonphim chấm com\nbên tui có bản đẹp nè, qua xem thử nha => vuonphim chấm com\nqua web bên tui ủng hộ nè, Vườn Phim á => vuonphim chấm com",
        "auto_comment_enabled": "0",
        "daily_limit": "25",         # Giới hạn an toàn chống ban tuyệt đối: tối đa 25 cmt/ngày
        "active_start": "08:00",     # Chỉ chạy từ 8h sáng
        "active_end": "23:00",       # Dừng lúc 23h đêm (tránh FB quét bot đêm)
        "session_duration_minutes": "0"  # Hẹn giờ tắt: 0 = chạy theo khung giờ, 60 = chạy 1 tiếng tự tắt
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))

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

# Luôn đảm bảo database và các bảng mặc định tồn tại khi import
init_db()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
