# Trạng thái: chạy thật, mô phỏng hay còn thiếu

Cập nhật 2026-10-16. Đã có backend thật (FastAPI + PostgreSQL + worker). Giao diện gọi backend thật;
dịch vụ nào chưa cấu hình / chưa khả dụng thì màn hình **ghi rõ**, không báo thành công giả.
Chưa thao tác lên tài khoản thật nào (chưa có khoá). Mọi dịch vụ ngoài trong kiểm thử đều là mock.

## Từng chức năng

| Chức năng | Chạy thật (đã kiểm) | Có code, chờ cấu hình để chạy thật | Chưa khả dụng / còn thiếu |
|---|---|---|---|
| PDF Manager | Upload lên server, chống trùng md5, **nhận diện + trích xuất Brazil CNPJ từ lớp chữ** (đúng trên 3 phôi thật), xem PDF gốc, sửa ô, kiểm tra hợp lệ ở server. **Luồng lưu chạy xuyên suốt giao diện → API → worker → PostgreSQL** với Google giả lập: kiểm trùng (DB + Sheet) → Drive (tìm theo md5 trước, không upload 2 lần) → md5 → Drive ID → dòng A, D–J (B, C trống) → K = “Xem phôi”; Sheet lỗi → chỉ ghi lại Sheet; tạm dừng/tiếp tục | Ghi Google thật — cần OAuth của anh (`scripts/google_auth.py`); bản scan: AI tự nhận diện loại phôi + đọc ô — cần ANTHROPIC_API_KEY | Wyoming: **chưa có phôi thật để kiểm** (bộ đọc lớp chữ theo nhãn + AI cho bản scan) |
| Tạo miền | 25 miền gốc của 3 nick, **tích chọn lưu trong database**, kiểm tra hosting chỉ đọc theo nick (cPanel `DomainInfo::list_domains` → miền gốc chưa có trên hosting thì không tích được; iNET `GET /domain` lưu nguyên dữ liệu để đối chiếu), chặn miền tạm ngưng / Cloudflare, khoá bỏ chọn miền đang có tác vụ, từ chối dòng gán miền chưa tích (kiểm lại ở server + trước mỗi bước tạo) | Quét Sheet (B trống) — cần Google; kiểm trùng cPanel + DNS, tạo miền phụ trên cPanel, xác minh DNS, đọc lại B rồi ghi — cần token cPanel | **Tạo bản ghi A qua API iNET**: tài liệu chưa có cấu trúc dữ liệu cho `PATCH /domain/{id}/record` → tác vụ dừng ở “Chưa khả dụng”. Đọc danh sách miền qua `GET /domain`: chưa biết cấu trúc trả về (đang dùng bản chép từ portal) |
| SSL + Tạo web | 15 mẫu, chọn mẫu tay lưu database, dựng HTML 6 trang theo **đúng mẫu đã chọn** (kiểm trong test) | Quét Sheet (B có, C trống) — cần Google; DNS, **document root đọc từ cPanel**, nội dung AI + kiểm tra không bịa, upload `overwrite=0`, AutoSSL, kiểm HTTPS, đọc lại C rồi ghi — cần token cPanel + ANTHROPIC_API_KEY | HTML gốc của 15 mẫu cũ chưa khôi phục (đang dựng lại từ tên, bảng màu, bố cục, từ khoá ảnh của app cũ) |
| Tổng quan | Giao diện | — | Vẫn là **dữ liệu mẫu** (có nhãn “Dữ liệu mẫu”) |
| Kho mẫu, Nhật ký, Cài đặt | — | — | Trang giữ chỗ. Khoá/token hiện đặt trong `apps/api/.env` |
| Nền tảng | Hàng đợi PostgreSQL (khoá chống chạy trùng, một việc/nick, thử lại có giãn cách, chạy tiếp từ bước dở, **tạm dừng/tiếp tục theo loại việc**), nhật ký từng việc, bảng `sheet_writes`, sao lưu/khôi phục `pg_dump` (đã kiểm khôi phục ra DB riêng) | Docker Compose (db, api, worker, web, backup) — **chưa chạy thử** vì máy này chưa có Docker | Đăng nhập/phân quyền; đẩy bản sao lưu ra kho ngoài (restic); đồng bộ GitHub Private (chưa có remote, chưa có `gh`) |

Kiểm thử: `apps/api` 39 test (mọi API ngoài đều mock) · hàng đợi chạy thật trên worker + PostgreSQL (chống trùng, tạm dừng, thử lại, khởi động lại giữ dữ liệu) · E2E PDF xuyên suốt với Google giả lập 12/12, tạm dừng/tiếp tục từ giao diện 4/4, các màn khác 14/14.

## API

| Dịch vụ | Đã dùng (theo tài liệu chính thức) | Thiếu |
|---|---|---|
| Google | OAuth 2.0 của chủ tài khoản (Desktop app, PKCE, quyền `spreadsheets` + `drive.file`) hoặc service account (chỉ Sheets / Shared Drive). Sheets v4 `values.get/update/append`, Drive v3 upload multipart + `appProperties` (tìm lại theo md5), tạo thư mục riêng của app | Tài khoản Gmail cá nhân: **service account không upload được vào Drive** (Google: “service accounts don't have storage quota”) → dùng OAuth |
| cPanel UAPI | `SubDomain::addsubdomain/listsubdomains`, `DomainInfo::single_domain_data/list_domains`, `Fileman::upload_files`, `SSL::start_autossl_check/is_autossl_check_in_progress/get_autossl_problems` | `DNS::mass_edit_zone` chưa làm (không miền gốc nào dùng NS cPanel) |
| iNET | `GET /domain` (gọi được, chưa parse) | Cấu trúc body `PATCH /domain/{id}/record`; cấu trúc trả về `GET /domain` |
| AI | Anthropic Messages (SDK `anthropic` 1.15, `claude-opus-5-5`, JSON schema, khối `document` cho PDF scan, fallback khi từ chối); `/api/ai/check` hỏi Models API xem model có với khoá không trước khi dùng | — (cần khoá) |

## Tối thiểu để kiểm thử thật

1. **Google** (Gmail cá nhân → OAuth): tạo OAuth client loại *Desktop app* trong Google Cloud (bật Sheets API + Drive API), tải file JSON,
   đặt `GOOGLE_OAUTH_CLIENT_FILE`, rồi **anh tự chạy** `python -m scripts.google_auth` để đồng ý một lần; `SHEET_ID` của **bản sao Sheet để thử**.
   `DRIVE_FOLDER_ID` để trống → app tự tạo thư mục “Quản Lí BM — Phôi PDF”.
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
