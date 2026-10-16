# Trạng thái: mô phỏng hay chạy thật

Cập nhật 2026-10-16. Toàn bộ giao diện hiện là **bản thiết kế bấm thử**: không gọi Google, iNET, cPanel, hosting hay AI.
Mỗi màn có nhãn "Bản thiết kế · dữ liệu giả"; nút/khối sẽ gọi dịch vụ ngoài có nhãn "Mô phỏng".

| Màn / chức năng | Đã có (chạy thật trong trình duyệt) | Đang mô phỏng — làm ở backend |
|---|---|---|
| Tổng quan | Giao diện, lọc, chọn dòng, phân trang | Đọc Google Sheet, số liệu, tiến trình module, nhật ký, sao lưu |
| PDF Manager | Kéo thả / chọn PDF, **xem trước PDF thật trên máy** (không gửi đi), kiểm tra định dạng & số kiểm tra CNPJ, chống trùng trong danh sách | Nhận diện loại phôi, đọc lớp chữ / AI OCR, upload Drive + md5, ghi Sheet, lưu database |
| Tạo miền iNET | Xem trước tên miền, kiểm tra nhãn DNS (a–z, 0–9, -, ≤63), phát hiện trùng trong danh sách, chia nick, kiểm tra form nick | Quét Sheet, tạo bản ghi A (iNET), tạo miền trên cPanel, xác minh DNS, đọc lại ô B rồi ghi, hạn mức nick, kiểm tra kết nối |
| SSL + Tạo web, Kho mẫu, Nhật ký, Cài đặt | — (trang giữ chỗ) | — |

## Quy tắc đã chốt

- PDF: Drive trước, lưu Drive ID, rồi ghi Sheet; Sheet lỗi → chỉ ghi lại Sheet. B, C trống; K = "Xem phôi".
- A, J bắt buộc; trường do AI đọc phải đối chiếu; trường thiếu phải xác nhận để trống; không tự bịa.
- Mã số (CNPJ, CEP, ZIP, Entity No., NÚMERO) giữ dạng văn bản, giữ số 0 đầu.
- California Entity No.: chỉ kiểm tra cơ bản, cảnh báo, **không chặn lưu** (chưa đủ mẫu để khẳng định cấu tạo).
- Ngành nghề suy từ tên công ty = **gợi ý, chưa xác minh**; từ CNAE = đọc từ phôi.
- Tự lưu PDF mặc định tắt.
- Dữ liệu thật (PDF, số CNPJ / Entity No. thật) không vào Git — chỉ ở `test-fixtures/` (bị ignore).
- Tạo miền = **tạo miền phụ trên miền gốc đã sở hữu**, không đăng ký domain mới. B chỉ ghi khi đủ: bản ghi A + miền trên cPanel +
  DNS trỏ đúng IP + ô B vẫn trống lúc ghi. Chỉ tạo DNS mà chưa có hosting ≠ thành công. Cột C không bao giờ bị ghi.

## Chờ chủ dự án chốt (Tạo miền)

1. Quy tắc tên miền phụ: bỏ hậu tố pháp lý (theo app cũ) hay dùng nguyên cột E — hay rút gọn kiểu `globalfreight` như ví dụ trong app cũ?
2. Danh sách nick thật: miền gốc, IP hosting, địa chỉ cPanel (hiện chỉ biết `th-ntp.com`).
3. iNET có API / token không, hay phải điều khiển trình duyệt như app cũ?
4. Mỗi nick có cPanel API token không? Hạn mức miền / ngày và tốc độ cho phép.
5. Cách chia nick mặc định: xoay vòng, ngẫu nhiên (app cũ) hay theo tay.
