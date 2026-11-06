import os
import re
import random
import base64
import requests
from core.db import get_setting

CASUAL_BRAND_PHRASES = [
    "ghé web tui flexphim xem phim nè",
    "qua web tui flexphim cày nha",
    "lên web tui flexphim coi bản nét căng á",
    "ghé web tui flexphim xem phim xả stress đi",
    "qua web tui flexphim kiếm thử nha",
    "bên web tui flexphim có full á",
    "tối rảnh ghé web tui flexphim cày nè",
    "coi trên web tui flexphim mượt đét luôn bạn ơi",
    "vô web tui flexphim xem bao dính á",
    "ghé web tui flexphim xem phim với tui nè",
    "lên web tui flexphim xem phim mượt đét nè bạn ơi"
]

VIETNAMESE_DIACRITICS = set(
    "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ"
)

COMMON_VN_WORDS = {
    "phim", "tôi", "tui", "mình", "bạn", "người", "không", "được", "nè", "nha", "á", "ạ",
    "nhé", "rồi", "xem", "coi", "ở", "có", "là", "và", "của", "với", "cho", "trong", "đang",
    "hay", "quá", "lắm", "thực", "thấy", "nhìn", "nói", "về", "ra", "vào", "đi", "lại",
    "tập", "rạp", "chiếu", "bộ", "cày", "diễn", "viên", "này", "kia", "đó", "hôm", "nay",
    "thế", "nào", "sao", "ơi", "uầy", "trời", "cuốn", "xỉu", "đỉnh", "chưa", "hả", "nghe",
    "cuối", "tuần", "vui", "buồn", "mệt", "tiền", "ăn", "uống", "nhà", "net"
}

def is_vietnamese_text(text):
    """
    Xác định chính xác 100% bài viết có phải tiếng Việt và của người Việt Nam hay không.
    Loại bỏ triệt để các bài viết tiếng Anh, tiếng Nhật, tiếng Thái hoặc bài viết nước ngoài.
    """
    if not text or len(text.strip()) < 8:
        return False
    # 1. Có dấu tiếng Việt đặc trưng -> Chắc chắn là tiếng Việt
    if any(c in VIETNAMESE_DIACRITICS for c in text):
        return True
    # 2. Nếu gõ không dấu, kiểm tra các từ vựng tiếng Việt phổ biến
    words = set(re.findall(r'\b\w+\b', text.lower()))
    matches = words.intersection(COMMON_VN_WORDS)
    return len(matches) >= 2

DEFAULT_BLOCKED_AUTHORS = [
    "chợ phim", "chophim", "cho phim",
    "tô phim", "tophim", "to phim",
    "sofaflix", "sofa flix", "sofa_flix"
]

def is_blocked_post(author="", url="", content=""):
    """
    Kiểm tra xem bài viết có thuộc các trang/kênh bị chặn né bình luận hay không
    (Ví dụ: chợ phim, tô phim, sofaflix...)
    Kiểm tra trên cả Tên tác giả, Username/Handle trên URL và Nội dung bài viết.
    """
    author_clean = (author or "").lower()
    url_clean = (url or "").lower()
    content_clean = (content or "").lower()

    # Trích xuất handle tài khoản từ URL (Threads hoặc X)
    handle = ""
    m_threads = re.search(r'/@([^/?]+)', url_clean)
    if m_threads:
        handle = m_threads.group(1).lower()
    else:
        m_x = re.search(r'(?:x|twitter)\.com/([^/?]+)/status/', url_clean)
        if m_x:
            handle = m_x.group(1).lower()

    raw_blocked = get_setting("blocked_authors", "")
    custom = [b.strip().lower() for b in raw_blocked.split(",") if b.strip()] if raw_blocked else []
    all_blocked = set(DEFAULT_BLOCKED_AUTHORS + custom)

    for bad in all_blocked:
        bad_clean = bad.strip().lower()
        if not bad_clean:
            continue
        # 1. Kiểm tra tên tác giả / display name
        if bad_clean in author_clean:
            return True
        # 2. Kiểm tra username/handle
        bad_nospace = bad_clean.replace(" ", "")
        if handle and (bad_nospace in handle or bad_clean in handle):
            return True
        if f"@{bad_nospace}" in url_clean or f"/{bad_nospace}/" in url_clean:
            return True
        # 3. Kiểm tra nội dung bài viết
        if bad_clean in content_clean:
            return True

    # Kiểm tra thêm blacklist keywords từ cài đặt
    blacklist_raw = get_setting("blacklist_keywords", "tuyển dụng, bán hàng, giá rẻ, vay tiền, scam, lừa đảo, cờ bạc")
    blacklist = [b.strip().lower() for b in blacklist_raw.split(",") if b.strip()]
    for bad in blacklist:
        if bad in content_clean or bad in author_clean or (handle and bad in handle):
            return True

    return False

class AIEngine:
    def __init__(self):
        pass

    @staticmethod
    def sanitize_comment(comment):
        """Lọc triệt để, không cho phép tên miền full (như .top, .com, chấm top, =>...) xuất hiện trong cmt"""
        if not comment:
            return ""
        # Xóa mũi tên => hoặc ->
        comment = re.sub(r'(=>|->)\s*', '', comment)
        # Xóa các dạng flexphim chấm top, flexphim.top, flexphim(.)top thành chỉ 'flexphim'
        comment = re.sub(r'flexphim\s*(?:\.|\s*chấm\s*|\s*\[chấm\]\s*|\s*\(\.\)\s*)(?:top|com|net|vn|xyz|me)', 'flexphim', comment, flags=re.IGNORECASE)
        comment = re.sub(r'flexphim\s+chấm\s+top', 'flexphim', comment, flags=re.IGNORECASE)
        comment = re.sub(r'\b(chấm top|\.top)\b', '', comment, flags=re.IGNORECASE)
        # Xóa link URL nếu còn sót
        comment = re.sub(r'https?://\S+', '', comment)
        # Dọn dẹp khoảng trắng
        comment = re.sub(r'\s+', ' ', comment).strip()
        return comment

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
            sample_defaults = [
                "Phim cuốn xỉu á, ghé web tui flexphim xem phim với tui nè!",
                "Tối rảnh ghé web tui flexphim xem phim xả stress nha bạn ơi!",
                "Bộ này bên web tui flexphim có bản nét căng luôn á, ghé cày thử nè!",
                "Ghé web tui flexphim xem phim bao mượt đét luôn á bạn ơi!",
                "Cuốn thực sự, tối qua web tui flexphim cày phim với tui nha!",
                "Lên web tui flexphim xem phim mượt đét khỏi lo giật lag nè bạn ơi!"
            ]
            return random.choice(sample_defaults)
        chosen_template = random.choice(lines)
        return AIEngine.parse_spintax(chosen_template)

    @classmethod
    def generate_comment(cls, post_text, fanpage_name="Fanpage", image_url=None, platform="mạng xã hội", is_general_post=False):
        """Sinh bình luận thông minh dựa trên nội dung bài viết và hình ảnh đính kèm (Gemini Multimodal Vision)"""
        api_key = get_setting("gemini_api_key", "").strip()

        # Nếu không có API Key, dùng Spintax thông minh
        if not api_key:
            return cls.sanitize_comment(cls.cloak_links(cls.get_fallback_comment()))

        topic = get_setting("topic", "Phim ảnh, review phim, giải trí")
        persona = get_setting("persona", "Bạn trẻ Gen Z mê phim, cmt siêu ngắn gọn (8-15 từ), xưng tui bạn bè thân mật, dùng từ lóng giới trẻ (cuốn xỉu, nét căng, mượt đét, bao dính), rủ ghé web tui flexphim xem phim")
        
        # Chọn ngẫu nhiên cụm từ nhắc thương hiệu tự nhiên (KHÔNG kèm tên web full)
        chosen_brand_phrase = random.choice(CASUAL_BRAND_PHRASES)

        brand_instruction = f"""
QUY TẮC BẮT BUỘC RỦ GHÉ "WEB TUI XEM PHIM":
- Bình luận BẮT BUỘC phải khéo léo đề cập rủ ghé web tui xem phim (ví dụ: "{chosen_brand_phrase}").
- Dùng các cụm từ tự nhiên như: "ghé web tui flexphim xem phim nè", "qua web tui flexphim cày nha", "bên web tui flexphim có full á", "ghé web tui flexphim xem phim với tui nè".
- TUYỆT ĐỐI KHÔNG viết tên miền hay link web (CẤM viết .top, .com, chấm top, =>, link...). Chỉ dùng chữ "web tui flexphim" hoặc "flexphim".
"""

        vision_instruction = ""
        if image_url and get_setting("gemini_vision_enabled", "1") == "1":
            vision_instruction = "LƯU Ý: Bài viết có ảnh đính kèm. Nhìn ảnh để nhận diện nhanh tên phim, diễn viên hoặc cảnh phim để cmt trúng nội dung!"

        fallback_style = ""
        if is_general_post:
            fallback_style = "ĐẶC BIỆT: Đây là bài viết thường văn bản (tâm sự, hài hước, đời sống). Cmt 1 câu ngắn gọn tự nhiên, đồng cảm hoặc pha trò rồi rủ tối ghé web tui flexphim xem phim xả stress."

        prompt = f"""
Bạn là: {persona}.
Chủ đề trọng tâm: {topic}.

Nhiệm vụ: Đọc bài viết sau trên {platform} và viết DUY NHẤT 1 CÂU BÌNH LUẬN SIÊU NGẮN GỌN (từ 8 đến 15 từ).

Bài viết:
\"\"\"{post_text}\"\"\"

{vision_instruction}
{fallback_style}

QUY TẮC BẮT BUỘC (TUÂN THỦ 100%):
1. ĐỘ DÀI: BẮT BUỘC DUY NHẤT 1 CÂU, CỰC KỲ NGẮN GỌN (từ 8 đến 15 từ). Tuyệt đối KHÔNG viết dài dòng lê thê hay 2-3 câu!
2. NGÔN NGỮ GIỚI TRẺ (Gen Z):
   - Xưng hô thân mật: "tui", "bạn ơi", thêm từ cảm thán: "nè", "nha", "á".
   - Dùng từ lóng tự nhiên của giới trẻ mê phim: "cuốn xỉu", "nét căng", "mượt đét", "bao dính", "xả stress", "cày phim".
   - Giọng điệu chân thật như một người bạn đang trò chuyện rủ rê xem phim.
3. {brand_instruction}
4. CÁC MẪU CÂU CHUẨN ĐỂ HỌC THEO:
   - "Phim cuốn xỉu á, tối ghé web tui flexphim xem phim nha bạn ơi!"
   - "Cảnh này bao dính luôn, ghé web tui flexphim xem phim nét căng nè!"
   - "Bộ này bên web tui flexphim có full á, ghé cày thử xả stress đi bạn ơi!"
   - "Mê bộ này ghê, tối rảnh ghé web tui flexphim xem phim với tui nè!"
   - "Coi trên web tui flexphim mượt đét luôn, tối ghé cày nha bạn ơi!"
5. CẤM TUYỆT ĐỐI: KHÔNG dùng đuôi tên miền (.top, .com, chấm top...), KHÔNG hashtag (#), KHÔNG câu sáo rỗng máy móc. Tối đa 1 icon.
6. ĐẦU RA: Chỉ trả về đúng 1 câu bình luận, không dấu ngoặc kép, không lời giải thích.
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

        payload = {
            "contents": [
                {
                    "parts": parts
                }
            ],
            "safetySettings": [
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ],
            "generationConfig": {
                "temperature": 0.88,
                "maxOutputTokens": 1000,
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash"]
        for m in models_to_try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            try:
                resp = requests.post(endpoint, json=payload, timeout=15)
                if resp.status_code == 200:
                    result = resp.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        resp_parts = candidates[0].get("content", {}).get("parts", [])
                        if resp_parts:
                            comment = resp_parts[0].get("text", "").strip()
                            comment = comment.strip('"').strip("'")
                            if comment:
                                if "flexphim" not in comment.lower():
                                    comment = f"{comment} Tối rảnh ghé web tui flexphim xem phim nha bạn ơi!"
                                return cls.sanitize_comment(cls.cloak_links(comment))
            except Exception:
                continue

        return cls.sanitize_comment(cls.cloak_links(cls.get_fallback_comment()))

if __name__ == "__main__":
    print("Test spintax:", AIEngine.get_fallback_comment())
