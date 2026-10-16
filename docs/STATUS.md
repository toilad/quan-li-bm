# Trạng thái: chạy thật, mô phỏng hay còn thiếu

Cập nhật 2026-10-16. Đã có backend thật (FastAPI + PostgreSQL + worker). Giao diện gọi backend thật;
dịch vụ nào chưa cấu hình / chưa khả dụng thì màn hình **ghi rõ**, không báo thành công giả.
Chưa thao tác lên tài khoản thật nào (chưa có khoá). Mọi dịch vụ ngoài trong kiểm thử đều là mock.

## Từng chức năng

| Chức năng | Chạy thật (đã kiểm) | Có code, chờ cấu hình để chạy thật | Chưa khả dụng / còn thiếu |
|---|---|---|---|
| PDF Manager | Upload PDF lên server, chống trùng md5, **nhận diện + trích xuất phôi Brazil CNPJ từ lớp chữ** (đúng trên 3 phôi thật, số kiểm tra CNPJ), xem PDF gốc, sửa ô, chọn loại phôi, kiểm tra hợp lệ phía server | Lưu: kiểm trùng (DB + Sheet) → Drive → md5 → Drive ID → ghi A, D–K (B, C trống, K = link) — cần Google; AI đọc bản scan California — cần ANTHROPIC_API_KEY | Wyoming: bộ đọc theo nhãn **chưa có phôi thật để kiểm** |
| Tạo miền | 25 miền gốc của 3 nick, **tích chọn lưu trong database**, chặn miền tạm ngưng / Cloudflare, khoá bỏ chọn miền đang có tác vụ, từ chối dòng gán miền chưa tích (kiểm lại ở server + trước mỗi bước tạo) | Quét Sheet (B trống) — cần Google; kiểm trùng cPanel + DNS, tạo miền phụ trên cPanel, xác minh DNS, đọc lại B rồi ghi — cần token cPanel | **Tạo bản ghi A qua API iNET**: tài liệu chưa có cấu trúc dữ liệu cho `PATCH /domain/{id}/record` → tác vụ dừng ở “Chưa khả dụng”. Đọc danh sách miền qua `GET /domain`: chưa biết cấu trúc trả về (đang dùng bản chép từ portal) |
| SSL + Tạo web | 15 mẫu, chọn mẫu tay lưu database, dựng HTML 6 trang theo **đúng mẫu đã chọn** (kiểm trong test) | Quét Sheet (B có, C trống) — cần Google; DNS, **document root đọc từ cPanel**, nội dung AI + kiểm tra không bịa, upload `overwrite=0`, AutoSSL, kiểm HTTPS, đọc lại C rồi ghi — cần token cPanel + ANTHROPIC_API_KEY | HTML gốc của 15 mẫu cũ chưa khôi phục (đang dựng lại từ tên, bảng màu, bố cục, từ khoá ảnh của app cũ) |
| Tổng quan | Giao diện | — | Vẫn là **dữ liệu mẫu** (có nhãn “Dữ liệu mẫu”) |
| Kho mẫu, Nhật ký, Cài đặt | — | — | Trang giữ chỗ. Khoá/token hiện đặt trong `apps/api/.env` |
| Nền tảng | Hàng đợi PostgreSQL (khoá chống chạy trùng, một việc/nick, thử lại có giãn cách, chạy tiếp từ bước dở), nhật ký từng việc, bảng `sheet_writes`, sao lưu/khôi phục `pg_dump` (đã kiểm khôi phục ra DB riêng) | Docker Compose (db, api, worker, web, backup) — **chưa chạy thử** vì máy này chưa có Docker | Đăng nhập/phân quyền; tạm dừng hàng đợi; đẩy bản sao lưu ra kho ngoài (restic); đồng bộ GitHub Private (chưa có remote, chưa có `gh`) |

Kiểm thử: `apps/api` 27 test (mọi API ngoài đều mock) · E2E giao diện ↔ backend thật: PDF 12/12, Tạo miền + SSL/Web 14/14.

## API

| Dịch vụ | Đã dùng (theo tài liệu chính thức) | Thiếu |
|---|---|---|
| Google | Sheets v4 `values.get/update/append` (RAW), Drive v3 upload multipart + `md5Checksum` | — (cần service account) |
| cPanel UAPI | `SubDomain::addsubdomain/listsubdomains`, `DomainInfo::single_domain_data`, `Fileman::upload_files`, `SSL::start_autossl_check/is_autossl_check_in_progress/get_autossl_problems` | `DNS::mass_edit_zone` chưa làm (không miền gốc nào dùng NS cPanel) |
| iNET | `GET /domain` (gọi được, chưa parse) | Cấu trúc body `PATCH /domain/{id}/record`; cấu trúc trả về `GET /domain` |
| AI | Anthropic Messages (SDK `anthropic`, `claude-opus-5-5`, JSON schema, fallback khi từ chối) | — (cần khoá) |

## Tối thiểu để kiểm thử thật

1. **Google**: 1 service account (file JSON), chia sẻ Sheet + thư mục Drive cho email của nó; `SHEET_ID`, `DRIVE_FOLDER_ID`.
   Nên dùng **bản sao Sheet để thử** trước khi chạy trên Sheet thật.
2. **AI**: `ANTHROPIC_API_KEY` (để đọc phôi scan và viết nội dung web).
3. **cPanel**: user + API token cho 3 tài khoản (`CPANEL_USER_N1..3`, `CPANEL_TOKEN_N1..3`).
4. **iNET**: khoá API quyền đọc (`INET_API_KEY_N1..3`) — để đọc cấu trúc `GET /domain`; tạo bản ghi A cần iNET cung cấp body của `PATCH /record`.
5. Mỗi lần thử thật đầu tiên trên một dịch vụ: em chỉ chạy **thao tác đọc** trước, anh duyệt rồi mới ghi.

## Quy tắc đã chốt

- **Mọi chức năng tự động bằng API** (Google, iNET, cPanel, AI). Không Playwright/Selenium, không bắt đăng nhập từng nick.
  Dịch vụ không có API phù hợp hoặc tài khoản thiếu quyền → báo "Chưa khả dụng"/"Chưa cấu hình", không thay bằng điều khiển trình duyệt.
  Endpoint chỉ lấy từ tài liệu chính thức — xem docs/API-RESEARCH.md.
- PDF: Drive trước, lưu Drive ID, rồi ghi Sheet; Sheet lỗi → chỉ ghi lại Sheet. B, C trống; K = link PDF gốc.
- A, J bắt buộc; trường do AI đọc phải đối chiếu; trường thiếu phải xác nhận để trống; không tự bịa.
- Mã số (CNPJ, CEP, ZIP, Entity No., NÚMERO) giữ dạng văn bản (ghi Sheet bằng RAW), giữ số 0 đầu.
- California Entity No.: chỉ kiểm tra cơ bản, cảnh báo, **không chặn lưu**.
- Ngành nghề suy từ tên công ty = **gợi ý**; từ CNAE = đọc từ phôi.
- Tự lưu PDF mặc định tắt. Dữ liệu thật (PDF, mã số thật) không vào Git — chỉ ở `test-fixtures/` (bị ignore).
- Tạo miền = **tạo miền phụ trên miền gốc đã sở hữu**. B chỉ ghi khi đủ: bản ghi A + miền trên cPanel + DNS trỏ đúng IP + ô B vẫn trống lúc ghi.
  Cột C không bao giờ bị ghi. Miền gốc phải có sẵn trên tài khoản cPanel (API `addsubdomain` yêu cầu).
- Miền gốc: hiện toàn bộ miền của nick, chỉ dùng miền đã tích; không tích sẵn; không tích → không chạy; không bỏ tích miền đang có tác vụ.
- Website: chỉ dòng có miền ở B và C trống. B chỉ đọc. Document root đọc từ cPanel, upload không ghi đè file có sẵn.
  C chỉ ghi khi https://B trả 200, chứng chỉ hợp lệ, đúng nội dung, và ô C vẫn trống lúc ghi.

## Chờ chủ dự án chốt

1. Quy tắc tên miền phụ: bỏ hậu tố pháp lý (app cũ, đang dùng) hay dùng nguyên cột E / rút gọn 2 từ.
2. `th-ntp.com` của app cũ thuộc nick nào.
3. Hạn mức miền / ngày mỗi nick (hiện không giới hạn).
