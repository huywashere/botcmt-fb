import os
import re
import random
import base64
import requests
from core.db import get_setting

class AIEngine:
    def __init__(self):
        pass

    @staticmethod
    def cloak_links(text):
        """Tự động lách link để chống Facebook Ghostban (biến domain.com thành domain chấm com)"""
        if get_setting("link_cloaking_enabled", "1") == "0":
            return text

        # Thay thế https:// hoặc http://
        text = re.sub(r'https?://(?:www\.)?', '', text, flags=re.IGNORECASE)

        # Thay thế các đuôi tên miền phổ biến
        domains = r'([a-zA-Z0-9-]+)\.(com|vn|net|org|cc|tv|me|xyz|top|site|club|vip)'
        cloaked_patterns = [
            r'\1 chấm \2',
            r'\1(.)\2',
            r'\1 [chấm] \2'
        ]
        chosen_cloak = random.choice(cloaked_patterns)
        text = re.sub(domains, chosen_cloak, text, flags=re.IGNORECASE)
        return text

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
    def generate_comment(cls, post_text, fanpage_name="Fanpage", image_url=None):
        """Sinh bình luận thông minh dựa trên nội dung bài viết và hình ảnh đính kèm (Gemini Multimodal Vision)"""
        api_key = get_setting("gemini_api_key", "").strip()

        # Nếu không có API Key, dùng Spintax thông minh
        if not api_key:
            return cls.cloak_links(cls.get_fallback_comment())

        topic = get_setting("topic", "Chia sẻ trải nghiệm, thảo luận vui vẻ")
        persona = get_setting("persona", "Đại diện Fanpage thân thiện, dí dỏm, trả lời ngắn gọn")
        brand = get_setting("brand_mention", "").strip()

        brand_instruction = ""
        if brand:
            brand_instruction = f"- Hãy khéo léo và tự nhiên nhắc đến: '{brand}' (ví dụ: 'ghé bên tui xem thử nè => {brand}', 'bên {brand} có bản nét nè bạn')."

        vision_instruction = ""
        if image_url and get_setting("gemini_vision_enabled", "1") == "1":
            vision_instruction = "LƯU Ý ĐẶC BIỆT: Bài viết này có hình ảnh đính kèm. Hãy quan sát ảnh để nhận diện tên bộ phim, diễn viên hoặc tình huống cảnh quay, từ đó viết bình luận chính xác tên phim và bối cảnh!"

        prompt = f"""
Bạn là: {persona} (Đại diện cho {fanpage_name}).
Chủ đề trọng tâm: {topic}.

Nhiệm vụ: Đọc bài viết sau trên Facebook về phim ảnh và viết 1 câu bình luận DUY NHẤT (tối đa 2 câu ngắn, dưới 30 từ).

Bài viết:
\"\"\"{post_text}\"\"\"

{vision_instruction}

Quy tắc vàng chống Spam & Tránh Facebook Checkpoint:
1. Giọng văn: Chuẩn người dùng trẻ Việt Nam mê phim, xưng hô tự nhiên (tui, mình, bạn ơi, nè, nha, coi cuốn lắm...).
2. Phản hồi trúng ý chính:
   - Nếu bài viết hỏi tìm phim/link xem/tập mới: Gợi ý nhiệt tình đúng nhu cầu hoặc trả lời tên phim nếu nhận diện được qua ảnh.
   - Nếu bài viết bàn luận về một bộ phim/diễn viên: Đưa ra góc nhìn chân thật của một mọt phim.
{brand_instruction}
3. Tuyệt đối KHÔNG viết câu sáo rỗng máy móc ('cảm ơn đã chia sẻ', 'bài viết hữu ích').
4. Tuyệt đối KHÔNG dùng hashtag (#), KHÔNG dùng quá 1 icon.
5. Chỉ trả về duy nhất chuỗi bình luận, không kèm ngoặc kép hay lời mở đầu.
"""

        parts = [{"text": prompt}]

        # Tải ảnh và đưa vào payload Multimodal nếu có
        if image_url and get_setting("gemini_vision_enabled", "1") == "1":
            try:
                img_resp = requests.get(image_url, timeout=6)
                if img_resp.status_code == 200:
                    b64_img = base64.b64encode(img_resp.content).decode("utf-8")
                    mime = "image/jpeg"
                    if ".png" in image_url.lower():
                        mime = "image/png"
                    parts.append({
                        "inline_data": {
                            "mime_type": mime,
                            "data": b64_img
                        }
                    })
            except Exception:
                pass

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "generationConfig": {
                "temperature": 0.85,
                "maxOutputTokens": 100
            }
        }

        try:
            resp = requests.post(endpoint, json=payload, timeout=18)
            if resp.status_code == 200:
                result = resp.json()
                candidates = result.get("candidates", [])
                if candidates:
                    resp_parts = candidates[0].get("content", {}).get("parts", [])
                    if resp_parts:
                        comment = resp_parts[0].get("text", "").strip()
                        comment = comment.strip('"').strip("'")
                        if comment:
                            return cls.cloak_links(comment)
            return cls.cloak_links(cls.get_fallback_comment())
        except Exception:
            return cls.cloak_links(cls.get_fallback_comment())

if __name__ == "__main__":
    print("Test spintax:", AIEngine.get_fallback_comment())

