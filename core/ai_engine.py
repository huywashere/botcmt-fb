import os
import re
import random
import requests
from core.db import get_setting

class AIEngine:
    def __init__(self):
        pass

    @staticmethod
    def test_gemini_connection(api_key=None):
        """Kiểm tra API Key của Gemini có hoạt động hay không"""
        if not api_key:
            api_key = get_setting("gemini_api_key", "").strip()

        if not api_key:
            return {"success": False, "message": "Chưa nhập API Key"}

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return {"success": True, "message": "Gemini Đã kết nối"}
            else:
                err_data = resp.json().get("error", {})
                return {"success": False, "message": err_data.get("message", f"Mã lỗi {resp.status_code}")}
        except Exception as e:
            return {"success": False, "message": f"Lỗi kết nối: {str(e)}"}

    @staticmethod
    def parse_spintax(text):
        """Phân giải chuỗi Spintax dạng {lựa chọn 1|lựa chọn 2|lựa chọn 3}"""
        pattern = re.compile(r'\{([^{}]+)\}')
        while True:
            match = pattern.search(text)
            if not match:
                break
            choices = match.group(1).split('|')
            chosen = random.choice(choices)
            text = text[:match.start()] + chosen + text[match.end():]
        return text

    @staticmethod
    def get_fallback_comment():
        """Lấy bình luận ngẫu nhiên từ danh sách mẫu Spintax đã cấu hình"""
        raw_samples = get_setting("spintax_samples", "")
        lines = [line.strip() for line in raw_samples.split("\n") if line.strip()]
        if not lines:
            return "Cảm ơn bạn đã chia sẻ thông tin bổ ích nha!"
        chosen_template = random.choice(lines)
        return AIEngine.parse_spintax(chosen_template)

    @classmethod
    def generate_comment(cls, post_text, fanpage_name="Fanpage"):
        """Sinh bình luận thông minh dựa trên nội dung bài viết"""
        api_key = get_setting("gemini_api_key", "").strip()

        # Nếu không có API Key, dùng Spintax thông minh
        if not api_key:
            return cls.get_fallback_comment()

        topic = get_setting("topic", "Chia sẻ trải nghiệm, thảo luận vui vẻ")
        persona = get_setting("persona", "Đại diện Fanpage thân thiện, dí dỏm, trả lời ngắn gọn")
        brand = get_setting("brand_mention", "").strip()

        brand_instruction = ""
        if brand:
            brand_instruction = f"- Nếu có cơ hội tự nhiên, hãy khéo léo giới thiệu hoặc nhắc đến: '{brand}'."

        prompt = f"""
Bạn là: {persona} (Đại diện cho {fanpage_name}).
Chủ đề chính: {topic}.

Nhiệm vụ: Viết 1 câu bình luận duy nhất (tối đa 2 câu ngắn) phản hồi cho bài viết sau trên mạng xã hội Facebook.

Nội dung bài viết:
\"\"\"{post_text}\"\"\"

Yêu cầu nghiêm ngặt:
1. Viết tự nhiên như một người dùng Việt Nam thật đang lướt mạng, xưng hô thân mật (mình/tui/bạn/nè/nha/ạ).
2. KHÔNG bình luận chung chung, sáo rỗng (như 'bài viết hay quá', 'cảm ơn admin').
3. Bắt đúng ý chính hoặc câu hỏi của bài viết để trả lời đúng trọng tâm.
{brand_instruction}
4. Tuyệt đối KHÔNG dùng hashtag, KHÔNG viết icon quá đà.
5. Chỉ trả về đúng nội dung bình luận, không kèm lời giải thích nào khác.
"""

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.85,
                "maxOutputTokens": 100
            }
        }

        try:
            resp = requests.post(endpoint, json=payload, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        comment = parts[0].get("text", "").strip()
                        # Làm sạch dấu ngoặc kép thừa nếu có
                        comment = comment.strip('"').strip("'")
                        if comment:
                            return comment
            # Nếu API lỗi hoặc hết quota -> fallback
            return cls.get_fallback_comment()
        except Exception:
            return cls.get_fallback_comment()

if __name__ == "__main__":
    print("Test spintax:", AIEngine.get_fallback_comment())
