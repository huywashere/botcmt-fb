import requests
from core.db import get_setting

class TelegramNotifier:
    @staticmethod
    def escape_html(text):
        if not text:
            return ""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def send_message(message, bot_token=None, chat_id=None):
        """Gửi thông báo đến Telegram cá nhân/nhóm"""
        if not bot_token:
            bot_token = get_setting("telegram_bot_token", "").strip()
        if not chat_id:
            chat_id = get_setting("telegram_chat_id", "").strip()

        if not bot_token or not chat_id:
            return False, "Chưa cấu hình Telegram Token hoặc Chat ID"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True, "Gửi thông báo thành công"
            else:
                return False, f"Telegram API Error: {resp.text}"
        except Exception as e:
            return False, f"Lỗi kết nối Telegram: {str(e)}"

    @staticmethod
    def test_connection(bot_token=None, chat_id=None):
        """Kiểm tra kết nối và gửi tin nhắn test đến Telegram cho Facebook"""
        msg = (
            "🔔 <b>[Facebook Page Auto Commenter]</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ Kết nối Telegram thành công!\n"
            "Hệ thống sẽ gửi thông báo mỗi khi bot bình luận hoặc gặp cảnh báo an toàn."
        )
        return TelegramNotifier.send_message(msg, bot_token, chat_id)

    @staticmethod
    def test_threads_connection(bot_token=None, chat_id=None):
        """Kiểm tra kết nối và gửi tin nhắn test đến Telegram cho Threads"""
        msg = (
            "🧵 <b>[Threads Auto Bot - Test Thông Báo]</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>Kết nối Telegram thành công!</b>\n"
            "Hệ thống Threads Auto Bot đã sẵn sàng gửi thông báo tức thì về điện thoại mỗi khi cmt xong."
        )
        return TelegramNotifier.send_message(msg, bot_token, chat_id)

    @staticmethod
    def notify_threads_comment(post_url, post_content, comment_text, author="", is_general=False, is_manual=False, today_count=0, daily_limit=30):
        """Gửi thông báo bình luận Threads đẹp mắt, chi tiết về Telegram"""
        author_escaped = TelegramNotifier.escape_html(author) if author else "Người dùng Threads"
        content_escaped = TelegramNotifier.escape_html(post_content[:200])
        comment_escaped = TelegramNotifier.escape_html(comment_text)
        
        mode_label = "Thủ công" if is_manual else "Tự động (Auto Bot)"
        type_label = "Bài viết thường văn bản 📝" if is_general else "Chủ đề Phim ảnh & Review 🎬"
        progress_str = f"{today_count}/{daily_limit} bài" if daily_limit > 0 else f"{today_count} bài"

        msg = (
            f"🧵 <b>[THREADS AUTO BOT - BÌNH LUẬN THÀNH CÔNG]</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Tác giả:</b> {author_escaped}\n"
            f"🏷️ <b>Phân loại:</b> {type_label}\n"
            f"⚙️ <b>Chế độ:</b> {mode_label}\n"
            f"📊 <b>Tiến độ Threads hôm nay:</b> <code>{progress_str}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📄 <b>Nội dung bài viết:</b>\n<i>\"{content_escaped}\"</i>\n\n"
            f"💬 <b>Bình luận đã gửi:</b>\n<b>{comment_escaped}</b>\n\n"
            f"🔗 <b>Xem bài viết Threads:</b>\n<a href=\"{post_url}\">{post_url}</a>"
        )
        return TelegramNotifier.send_message(msg)

    @staticmethod
    def test_x_connection(bot_token=None, chat_id=None):
        """Kiểm tra kết nối và gửi tin nhắn test đến Telegram cho X (Twitter)"""
        msg = (
            "𝕏 <b>[X (Twitter) Auto Bot - Test Thông Báo]</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>Kết nối Telegram thành công!</b>\n"
            "Hệ thống X (Twitter) Auto Bot đã sẵn sàng gửi thông báo tức thì về điện thoại mỗi khi cmt xong."
        )
        return TelegramNotifier.send_message(msg, bot_token, chat_id)

    @staticmethod
    def notify_x_comment(post_url, post_content, comment_text, author="", is_general=False, is_manual=False, today_count=0, daily_limit=25):
        """Gửi thông báo bình luận X (Twitter) đẹp mắt, chi tiết về Telegram"""
        author_escaped = TelegramNotifier.escape_html(author) if author else "Người dùng 𝕏"
        content_escaped = TelegramNotifier.escape_html(post_content[:200])
        comment_escaped = TelegramNotifier.escape_html(comment_text)
        
        mode_label = "Thủ công" if is_manual else "Tự động (Auto Bot)"
        type_label = "Bài viết thường văn bản 📝" if is_general else "Chủ đề Phim ảnh & Review 🎬"
        progress_str = f"{today_count}/{daily_limit} bài" if daily_limit > 0 else f"{today_count} bài"

        msg = (
            f"𝕏 <b>[X (TWITTER) AUTO BOT - BÌNH LUẬN THÀNH CÔNG]</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Tác giả Tweet:</b> {author_escaped}\n"
            f"🏷️ <b>Phân loại:</b> {type_label}\n"
            f"⚙️ <b>Chế độ:</b> {mode_label}\n"
            f"📊 <b>Tiến độ 𝕏 hôm nay:</b> <code>{progress_str}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📄 <b>Nội dung Tweet:</b>\n<i>\"{content_escaped}\"</i>\n\n"
            f"💬 <b>Bình luận đã gửi:</b>\n<b>{comment_escaped}</b>\n\n"
            f"🔗 <b>Xem Tweet trên 𝕏:</b>\n<a href=\"{post_url}\">{post_url}</a>"
        )
        return TelegramNotifier.send_message(msg)
