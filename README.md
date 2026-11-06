# Facebook & Threads Auto Commenter - Pro Edition 🚀

Phần mềm tự động bình luận chuyên nghiệp đa nền tảng cho **Facebook Fanpage** và **Threads (`threads.net`)** với giao diện Desktop hiện đại, tích hợp **AI Gemini 2.5 Flash** phân tích ngữ cảnh bài viết để tự động cào bài thảo luận phim ảnh, tạo bình luận người thật độc nhất, quảng bá thương hiệu tự nhiên, chống spam và tránh checkpoint tối đa.

---

## 🌟 Tính Năng Nổi Bật

1. **🧵 Threads Auto Bot - Tự Động Cào Chủ Đề Phim & Bình Luận Thông Minh**:
   - Tự động cào các bài thảo luận về phim ảnh mới nhất trên Threads (từ khóa: *phim, review phim, web phim, netflix, cày phim, mọt phim, phim bộ*).
   - Gemini AI đọc ngữ cảnh từng bài và viết câu trả lời dí dỏm, khéo léo giới thiệu thương hiệu `flexphim chấm top`.
   - Lưu trữ phiên đăng nhập Threads độc lập trong thư mục `threads_user_data/` (không ảnh hưởng Facebook).
   - Nút **"Đăng nhập Threads"** mở Chrome thật để bạn đăng nhập tài khoản một lần vĩnh viễn.

2. **⚡ Facebook Page Auto Commenter**:
   - Tự động nhận diện và chuyển đổi ngữ cảnh bình luận dưới danh nghĩa **Fanpage** (Meta New Pages Experience).
   - Quét Newsfeed, Groups hoặc danh sách URL chỉ định.
   - Cơ chế làm ấm session (Pre-Action Warm-Up) và tự động lách link chống Ghostban.

3. **Công nghệ AI Gemini 2.5 Flash**:
   - Tự đọc nội dung bài viết và hình ảnh poster phim (Multimodal Vision).
   - Tự động sinh câu bình luận ngắn gọn, tự nhiên như người dùng mạng xã hội thực thụ (tối đa 25-30 từ).
   - Khéo léo nhắc đến thương hiệu: `qua Flex Phim thử đi nè => flexphim chấm top`.

4. **Kỹ thuật Giả lập Người thật & Anti-Checkpoint**:
   - **Playwright Chromium Stealth**: Ẩn dấu vết webdriver, chạy 100% ngầm (headless) không làm phiền màn hình.
   - **Jitter Delay (~2 phút/bài)**: Giãn cách an toàn 110s - 130s giữa các bài viết với đồng hồ đếm ngược trực tiếp.
   - **Gõ phím ngẫu nhiên (Human Typing)**: Mô phỏng tốc độ gõ phím của người thật.
   - **Thông báo Telegram Bot**: Gửi thông báo tức thì về điện thoại kèm trích đoạn bài viết, nội dung bình luận và link bài.
   - **Xuất báo cáo Excel/CSV**: Xuất lịch sử bình luận Facebook và Threads với mã hóa tiếng Việt chuẩn `utf-8-sig`.

---

## 🛠️ Cấu Trúc Dự Án

```
c:\bot-cmt fb\
├── main.py                     # Khởi chạy ứng dụng Desktop (PyWebView)
├── run.bat                     # File kích hoạt nhanh bằng 1 click trên Windows
├── requirements.txt            # Danh sách thư viện Python cần thiết
├── core/
│   ├── db.py                   # Quản lý cơ sở dữ liệu SQLite
│   ├── ai_engine.py            # Kết nối Google Gemini API & Phân giải Spintax
│   ├── browser_engine.py       # Tự động hóa Playwright Chromium Stealth
│   └── bot_worker.py           # Điều phối lịch trình quét và bình luận ngẫu nhiên
└── web/                        # Giao diện người dùng Desktop (Tailwind CSS)
    ├── index.html              # Khung giao diện chính
    └── js/
        └── app.js              # Xử lý logic giao diện và kết nối API
```

---

## 🚀 Hướng Dẫn Sử Dụng

### Bước 1: Khởi động phần mềm
- Nhấp đúp vào file `run.bat` (hoặc chạy lệnh `python main.py` trong terminal).

### Bước 2: Đăng nhập Facebook
- Vào tab **Tài khoản & Page** -> Bấm **"Mở trình duyệt đăng nhập Facebook"**.
- Trình duyệt Chrome sẽ mở ra để bạn đăng nhập tài khoản sở hữu Fanpage và xác thực 2FA.
- Sau khi đăng nhập xong, bạn có thể đóng trình duyệt; phiên đăng nhập đã được tự động lưu.

### Bước 3: Cấu hình AI & Kịch bản
- Vào tab **Cài đặt Anti-Ban** -> Nhập **Google Gemini API Key** (lấy miễn phí tại [aistudio.google.com](https://aistudio.google.com)).
- Vào tab **Soạn bài & Kịch bản** -> Nhập chủ đề, giọng văn và từ khóa mong muốn.

### Bước 4: Chạy bình luận
- Vào tab **Newsfeed**:
  - Chọn tần suất quét (ví dụ: `5 phút`).
  - Bấm **"Quét thử - chưa gửi"** để xem trước AI sinh bình luận thế nào.
  - Bấm **"Bật tự bình luận"** để hệ thống tự động làm việc theo lịch trình.

