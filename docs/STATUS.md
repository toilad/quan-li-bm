# Trạng thái: mô phỏng hay chạy thật

Cập nhật 2026-10-16. Toàn bộ giao diện hiện là **bản thiết kế bấm thử**: không gọi Google, iNET, cPanel, hosting hay AI.
Mỗi màn có nhãn "Bản thiết kế · dữ liệu giả"; nút/khối sẽ gọi dịch vụ ngoài có nhãn "Mô phỏng".

| Màn / chức năng | Đã có (chạy thật trong trình duyệt) | Đang mô phỏng — làm ở backend |
|---|---|---|
| Tổng quan | Giao diện, lọc, chọn dòng, phân trang | Đọc Google Sheet, số liệu, tiến trình module, nhật ký, sao lưu |
| PDF Manager | Kéo thả / chọn PDF, **xem trước PDF thật trên máy** (không gửi đi), kiểm tra định dạng & số kiểm tra CNPJ, chống trùng trong danh sách | Nhận diện loại phôi, đọc lớp chữ / AI OCR, upload Drive + md5, ghi Sheet, lưu database |
| Tạo miền iNET | 3 nick thật, **toàn bộ tên miền của từng nick, mỗi miền 1 ô tích** (chọn/bỏ chọn theo nick hoặc tất cả), lưu lựa chọn cho lần sau (bản thiết kế: trình duyệt), khoá bỏ chọn miền đang có tác vụ, chặn miền tạm ngưng / hết hạn / DNS ngoài iNET, cảnh báo sắp hết hạn, phân bổ công ty vào các miền đã tích (xoay vòng đan xen nick / tỷ trọng nick / dồn 1 miền), đổi miền gốc từng dòng trong các miền đã tích, không có miền nào được tích → không cho chạy, xem trước & sửa tên miền, 3 cách tạo tên, đánh dấu dòng thiếu K (không loại), giới hạn mỗi lượt tách khỏi hạn mức nick, chặn khi nick thiếu quyền API, lưu tài nguyên khi ô B xung đột, kiểm tra nhãn DNS (a–z, 0–9, -, ≤63), phát hiện trùng trong danh sách, chia nick, kiểm tra form nick | Đọc danh sách tên miền qua API iNET, lưu lựa chọn miền vào database, quét Sheet, tạo bản ghi A (iNET), tạo miền trên cPanel, xác minh DNS, đọc lại ô B rồi ghi, hạn mức nick, kiểm tra kết nối |
| SSL + Tạo web | Lọc dòng B có miền + C trống, xác định hosting từ danh sách miền của nick, nhận diện ngành (hiện từ khoá khớp), 15 mẫu cũ — đổi từng dòng hoặc áp hàng loạt, xem trước website, hộp xác nhận trước khi chạy, không tự chạy khi mở trang, chọn AI (Claude / OpenAI + dự phòng), tiến trình 9 bước, xác minh document root qua cPanel API trước khi upload (không đoán đường dẫn), xem trước toàn trang từng mẫu theo bố cục riêng, ghi lại mẫu thực sự dùng để dựng, thử lại từ bước lỗi không upload lại, chặn khi DNS của B không trỏ đúng IP, loại nội dung AI có số liệu bịa rồi tạo lại, chỉ ghi C khi HTTPS chạy thật và ô C còn trống, lưu “Website chưa gắn” khi ô C xung đột | Đọc Sheet, gọi AI, dựng HTML thật, upload (cPanel Fileman / FTPS), AutoSSL, kiểm tra HTTPS, ghi C |
| Kho mẫu, Nhật ký, Cài đặt | — (trang giữ chỗ) | — |

## Quy tắc đã chốt

- **Mọi chức năng tự động bằng API** (Google, iNET, cPanel, AI). Không Playwright/Selenium, không bắt đăng nhập từng nick.
  Dịch vụ không có API phù hợp hoặc tài khoản thiếu quyền → báo "Bị chặn", không thay bằng điều khiển trình duyệt.
  Endpoint chỉ lấy từ tài liệu chính thức — xem docs/API-RESEARCH.md.

- PDF: Drive trước, lưu Drive ID, rồi ghi Sheet; Sheet lỗi → chỉ ghi lại Sheet. B, C trống; K = "Xem phôi".
- A, J bắt buộc; trường do AI đọc phải đối chiếu; trường thiếu phải xác nhận để trống; không tự bịa.
- Mã số (CNPJ, CEP, ZIP, Entity No., NÚMERO) giữ dạng văn bản, giữ số 0 đầu.
- California Entity No.: chỉ kiểm tra cơ bản, cảnh báo, **không chặn lưu** (chưa đủ mẫu để khẳng định cấu tạo).
- Ngành nghề suy từ tên công ty = **gợi ý, chưa xác minh**; từ CNAE = đọc từ phôi.
- Tự lưu PDF mặc định tắt.
- Dữ liệu thật (PDF, số CNPJ / Entity No. thật) không vào Git — chỉ ở `test-fixtures/` (bị ignore).
- Tạo miền = **tạo miền phụ trên miền gốc đã sở hữu**, không đăng ký domain mới. B chỉ ghi khi đủ: bản ghi A + miền trên cPanel +
  DNS trỏ đúng IP + ô B vẫn trống lúc ghi. Chỉ tạo DNS mà chưa có hosting ≠ thành công. Cột C không bao giờ bị ghi.
- Miền gốc (yêu cầu chính thức 16/10/2026, thay thiết kế 1 miền / nick): không giới hạn số miền mỗi nick. App hiện toàn bộ miền của nick
  (lấy qua API), chủ dự án tích miền nào thì chỉ dùng miền đó. Miền tạm ngưng / hết hạn / API không ghi được DNS → không tích được, không chạy.
  Không tích miền nào → không bắt đầu. Đổi lựa chọn bất cứ lúc nào, trừ miền đang có dòng chạy hoặc đã tạo DNS chưa ghi B.

- Website: chỉ lấy dòng có miền ở B và C trống. B chỉ đọc. C chỉ ghi khi https://B trả 200, chứng chỉ hợp lệ, đúng nội dung, và ô C vẫn trống lúc ghi.
  Nội dung AI chỉ dùng dữ kiện từ Sheet (A, D, F–I, J); không bịa giải thưởng / khách hàng / số liệu.

## Cần để chạy thật (SSL + Tạo web)

1. Khoá AI API (Anthropic và/hoặc OpenAI) — nhập ở server; chọn model ở Cài đặt API.
2. cPanel API token cho từng hosting (3 tài khoản trên 2 server); xác nhận AutoSSL đã bật ở WHM.
3. Khôi phục renderer HTML 15 mẫu từ bytecode app cũ. Bản xem trước hiện tại dựng lại gần đúng (tên, bảng màu, 6 kiểu bố cục, từ khoá ảnh lấy từ app cũ), chưa phải HTML gốc.
4. Backend: hàng đợi chạy trên server, ghi Sheet qua Google Sheets API, database lưu tiến trình & “Website chưa gắn”.

## Chờ chủ dự án chốt (Tạo miền)

1. Quy tắc tên miền phụ: bỏ hậu tố pháp lý (theo app cũ) hay dùng nguyên cột E — hay rút gọn kiểu `globalfreight` như ví dụ trong app cũ?
2. ✔ Đã có 3 nick thật (đọc portal iNET 16/10/2026, chỉ đọc): iNET-1, iNET-2 cùng hosting cPanel 103.75.187.26; iNET-3 ở 202.92.7.88.
   Gần như mọi miền gốc dùng nameserver iNET → bản ghi A đi qua API DNS iNET. `167nailspa.com` dùng DNS Cloudflare → bị chặn; `vietcart.site` tạm ngưng.
   Miền dùng để tạo miền phụ: chủ dự án tự tích trong app (mặc định lần đầu: các miền đã trỏ hosting). Còn chờ: `th-ntp.com` của app cũ thuộc nick nào.
   User cPanel không đưa vào Git. **Cần xác minh trong tài liệu iNET: endpoint liệt kê tên miền của tài khoản** (chưa có trong docs/API-RESEARCH.md).
3. Toàn bộ chạy qua API (không điều khiển trình duyệt) — xem câu hỏi trong docs/API-RESEARCH.md (cPanel token, AutoSSL, khoá iNET write).
4. Mỗi nick có cPanel API token không? Hạn mức miền / ngày và tốc độ cho phép.
5. Cách phân bổ mặc định: xoay vòng các miền đã tích (đan xen nick, đang dùng), theo tỷ trọng nick, hay ngẫu nhiên như app cũ.
