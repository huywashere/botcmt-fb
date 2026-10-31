import requests
from core.db import get_setting

class TelegramNotifier:
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
            "disable_web_page_preview": True
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
    def test_connection(bot_token, chat_id):
        """Kiểm tra kết nối và gửi tin nhắn test đến Telegram"""
        msg = (
            "🔔 <b>[Facebook Page Auto Commenter]</b>\n"
            "✅ Kết nối Telegram thành công!\n"
            "Hệ thống sẽ gửi thông báo mỗi khi bot bình luận hoặc gặp cảnh báo an toàn."
        )
        return TelegramNotifier.send_message(msg, bot_token, chat_id)
