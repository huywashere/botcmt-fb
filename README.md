# Facebook Page Auto Commenter - Pro Edition 🚀

Phần mềm tự động bình luận Facebook chuyên dụng cho **Fanpage** với giao diện Desktop hiện đại, tích hợp **AI Gemini** phân tích ngữ cảnh bài viết để tạo bình luận người thật độc nhất, chống spam và tránh checkpoint tối đa.

---

## 🌟 Tính Năng Nổi Bật

1. **Giao diện Desktop hiện đại**:
   - Thiết kế chuẩn Dark Mode (tương tự Threads Auto Poster / Meta Suite).
   - Bảng theo dõi lịch sử bình luận thời gian thực với đầy đủ thông tin: Bài gốc, Nội dung bình luận, Trạng thái (`Đã gửi`, `Quét thử`, `Lỗi`).
   - Cột xem trước bài viết được chọn và trình chỉnh sửa bình luận dự kiến.

2. **Cơ chế hoạt động dạng Fanpage**:
   - Tự động nhận diện và chuyển đổi ngữ cảnh bình luận dưới danh nghĩa **Fanpage** (Meta New Pages Experience).
   - Mở trình duyệt thật để người dùng đăng nhập tài khoản một lần duy nhất, vượt 2FA an toàn và lưu phiên làm việc (Session/Cookies) tại máy cục bộ.

3. **Công nghệ AI tránh Spam 100%**:
   - **Google Gemini 1.5/2.0 API**: Tự động đọc tiêu đề và nội dung bài viết, phân tích ngữ cảnh để sinh bình luận tiếng Việt tự nhiên như người dùng thật.
   - **Cấu hình Persona & Topic**: Thiết lập tính cách Fanpage (hài hước, chuyên gia, thân thiện) và khéo léo chèn thương hiệu/sản phẩm nếu cần.
   - **Bộ lọc từ khóa (Keywords Filter)**: Chỉ bình luận vào các bài viết có chủ đề hoặc từ khóa liên quan.
   - **Mẫu Spintax dự phòng**: Hỗ trợ cú pháp `{từ 1|từ 2}` hoạt động độc lập ngay cả khi không dùng API Key.

4. **Kỹ thuật Giả lập Người thật & Anti-Checkpoint**:
   - Sử dụng **Playwright Chromium Stealth**: Ẩn dấu vết webdriver, bảo vệ tài khoản khỏi thuật toán quét bot của Facebook.
   - **Jitter Delay**: Độ trễ ngẫu nhiên giữa các lần bình luận (ví dụ 120s – 300s).
   - **Gõ phím ngẫu nhiên (Human Typing)**: Mô phỏng tốc độ gõ từng ký tự của người thật.
   - **Khung giờ hoạt động an toàn**: Tự động nghỉ ngoài giờ và kiểm soát hạn mức bình luận mỗi ngày.

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

