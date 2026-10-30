import sqlite3
import os
import json
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

    # Pre-populate default settings
    default_settings = {
        "gemini_api_key": "",
        "scan_interval": "5",       # 5 minutes
        "feed_source": "for_you",    # for_you, groups, custom_urls
        "min_delay": "120",          # seconds
        "max_delay": "300",          # seconds
        "topic": "Đánh giá, chia sẻ kinh nghiệm, thảo luận tích cực",
        "persona": "Đại diện Fanpage thân thiện, hiểu biết, đưa ra lời khuyên chân thực và hữu ích.",
        "brand_mention": "",
        "keywords": "",              # Từ khóa lọc bài viết (phân cách bằng dấu phẩy)
        "spintax_samples": "qua Vườn Phim thử đi nè, web bên tui làm á => vuonphim chấm com\nghé bên tui chơi thử xem sao nha, Vườn Phim nè => vuonphim chấm com\nbên tui là Vườn Phim nè, qua tìm thử phim bạn thích nha => vuonphim chấm com",
        "auto_comment_enabled": "0",
        "daily_limit": "25",
        "active_start": "08:00",
        "active_end": "23:00"
    }

    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

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
