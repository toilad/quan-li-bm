# Trạng thái: chạy thật, mô phỏng hay còn thiếu

Cập nhật 2026-10-17. Đã có backend thật (FastAPI + PostgreSQL + worker). Giao diện gọi backend thật;
dịch vụ nào chưa cấu hình / chưa khả dụng thì màn hình **ghi rõ**, không báo thành công giả.
Chưa thao tác lên tài khoản thật nào (chưa có khoá). Mọi dịch vụ ngoài trong kiểm thử đều là mock.

## Từng chức năng

| Chức năng | Chạy thật (đã kiểm) | Có code, chờ cấu hình để chạy thật | Chưa khả dụng / còn thiếu |
|---|---|---|---|
| PDF Manager | Upload lên server, chống trùng md5, **nhận diện + trích xuất Brazil CNPJ từ lớp chữ** (đúng trên 3 phôi thật, kiểm số kiểm tra CNPJ), xem PDF gốc, sửa ô, kiểm tra hợp lệ ở server. **Luồng lưu chạy xuyên suốt giao diện → API → worker → PostgreSQL** với Google giả lập: kiểm trùng (DB + Sheet) → Drive (tìm theo md5 trước, không upload 2 lần) → md5 → Drive ID → dòng A, D–J (B, C trống) → K = “Xem phôi”; Sheet lỗi → chỉ ghi lại Sheet; tạm dừng/tiếp tục. Ô tick **“email liên hệ chính thức (đã xác minh)”** trên thẻ CNPJ | Ghi Google thật — cần OAuth của anh; bản scan (California): AI nhận diện + đọc ô, **đối chiếu số hồ sơ và tên với bản in lại ở trang sau** (khác số → chặn lưu tới khi anh sửa tay) — cần ANTHROPIC_API_KEY | Wyoming: **chưa có phôi thật để kiểm** |
| Tạo miền | 25 miền gốc của 3 nick, **tích chọn lưu trong database**, kiểm tra nick chỉ đọc (cPanel `DomainInfo::list_domains` + **phiên bản cPanel**; iNET `GET /domain`), chặn miền tạm ngưng / Cloudflare, khoá bỏ chọn miền đang có tác vụ, từ chối dòng gán miền chưa tích | Quét Sheet (B trống) — cần Google; kiểm trùng cPanel + DNS, tạo miền phụ trên cPanel, xác minh DNS, đọc lại B rồi ghi — cần token cPanel | **Tạo bản ghi A qua iNET**: tài liệu chính thức nay **đã có** cấu trúc `PATCH /domain/{id}/record` (ACTION_ADD). Code **vẫn chặn**, chờ anh duyệt bật ghi DNS thật |
| SSL + Tạo web | **Mẫu web gốc của app cũ đã khôi phục** từ EXE và dùng để dựng 6 trang + robots/sitemap; xem trước = đúng HTML sẽ dựng. **Email chỉ hiện khi đã xác minh**; chưa xác minh/không có → không có link email, không có form gửi thư (thay bằng gọi điện/địa chỉ) | Quét Sheet (B có, C trống) — cần Google; document root đọc từ cPanel, nội dung AI + kiểm tra không bịa, upload `overwrite=0`, AutoSSL, kiểm HTTPS, đọc lại C rồi ghi — cần token cPanel + ANTHROPIC_API_KEY | — |
| Cài đặt API | Trang **Cài đặt API**: Google, AI, máy chủ, iNET/cPanel × 3 nick. Khoá **mã hoá ở server** (Fernet, khoá chủ `data/master.key` hoặc `QLBM_MASTER_KEY`), không bao giờ trả về giao diện hay ghi log. Nút **Kết nối Google** (OAuth web, PKCE) + kiểm tra Google chỉ đọc | OAuth client loại *Web application* + redirect URI của server | — |
| Tổng quan | Giao diện | — | Vẫn là **dữ liệu mẫu** (có nhãn “Dữ liệu mẫu”) |
| Nền tảng | Hàng đợi PostgreSQL (chống chạy trùng, một việc/nick, thử lại có giãn cách, chạy tiếp từ bước dở, tạm dừng/tiếp tục), nhật ký từng việc, bảng `sheet_writes`, sao lưu/khôi phục `pg_dump`; **khởi động lại API + worker giữ nguyên dữ liệu và việc dở** | Docker Compose (db, api, worker, web, backup) — **chưa chạy thử** (máy này chưa có Docker) | **API chưa có đăng nhập/phân quyền** — không được mở ra Internet trước khi có; GitHub Private (chưa có remote) |

Kiểm thử: `apps/api` **67 test**, mọi API ngoài đều mock, gồm **1 test toàn tuyến** trên cùng một Sheet giả: lưu PDF → tạo miền (B) → dựng web (C).
Trong test này chỉ bước ghi DNS iNET là hàm giả. E2E giao diện trên backend dev: các màn 14/14, Cài đặt 11/11, xác minh email 6/6, xem trước 15 mẫu 15/15.

## API

| Dịch vụ | Đã dùng (theo tài liệu chính thức) | Thiếu |
|---|---|---|
| Google | OAuth 2.0 của chủ tài khoản (web PKCE từ trang Cài đặt; script Desktop chỉ để phát triển), quyền `spreadsheets` + `drive.file`. Sheets v4 `values.get/update/append`, Drive v3 upload multipart + `appProperties` | Gmail cá nhân: service account không upload được vào Drive → dùng OAuth |
| cPanel UAPI | `SubDomain::addsubdomain/listsubdomains`, `DomainInfo::single_domain_data/list_domains`, `Fileman::upload_files`, `SSL::start_autossl_check/is_autossl_check_in_progress/get_autossl_problems`, `StatsBar::get_stats` (cpanelversion) | `DNS::mass_edit_zone` chưa làm (không miền gốc nào dùng NS cPanel) |
| iNET | `GET /domain` (đã có cấu trúc trả về trong tài liệu) | Ghi `PATCH /domain/{id}/record`: tài liệu đủ, **chờ anh duyệt** bật |
| AI | Anthropic Messages (SDK `anthropic` 1.15, `claude-opus-5-5`, JSON schema, khối `document` cho PDF scan, fallback khi từ chối); `/api/ai/check` | — (cần khoá) |

## Tối thiểu để kiểm thử thật

1. **Google**: OAuth client loại **Web application** (bật Sheets API + Drive API), redirect URI = `PUBLIC_API_URL/api/google/oauth/callback`
   (trang Cài đặt hiện sẵn). Dán JSON client ở trang Cài đặt → bấm **Kết nối Google**. `SHEET_ID` của **bản sao Sheet để thử**.
2. **AI**: `ANTHROPIC_API_KEY`.
3. **cPanel**: user + API token cho 3 tài khoản.
4. **iNET**: khoá API — `read` để kiểm tra nick; `write` chỉ khi anh duyệt bật tạo bản ghi A.
5. Mỗi lần thử thật đầu tiên trên một dịch vụ: em chỉ chạy **thao tác đọc** trước, anh duyệt rồi mới ghi.

## Quy tắc đã chốt

- **Mọi chức năng tự động bằng API** (Google, iNET, cPanel, AI). Không Playwright/Selenium, không bắt đăng nhập từng nick.
  Endpoint chỉ lấy từ tài liệu chính thức — xem docs/API-RESEARCH.md.
- PDF: Drive trước, lưu Drive ID, rồi ghi Sheet; Sheet lỗi → chỉ ghi lại Sheet. B, C trống; K = link PDF gốc.
- A, J bắt buộc; trường do AI đọc phải đối chiếu; trường thiếu phải xác nhận để trống; không tự bịa.
- Mã số (CNPJ, CEP, ZIP, Entity No.) giữ dạng văn bản (ghi Sheet bằng RAW), giữ số 0 đầu.
- California: số hồ sơ 12 chữ số chỉ cảnh báo; **khác bản in lại ở trang sau → chặn lưu**; không thấy bản in lại → cảnh báo.
- Email: Sheet **không thêm cột email**. Web chỉ dùng email trên phôi khi anh đã tick xác minh là email chính thức; không thì ẩn email và form.
- Ngành nghề suy từ tên công ty = **gợi ý**; từ CNAE = đọc từ phôi.
- Tự lưu PDF mặc định tắt. Dữ liệu thật (PDF, mã số thật) không vào Git — chỉ ở `test-fixtures/` (bị ignore).
- Tạo miền = **tạo miền phụ trên miền gốc đã sở hữu**. B chỉ ghi khi đủ: bản ghi A + miền trên cPanel + DNS trỏ đúng IP + ô B vẫn trống lúc ghi.
- Miền gốc: hiện toàn bộ miền của nick, chỉ dùng miền đã tích; không tích sẵn; không tích → không chạy.
- Mẫu cũ, những phần **không xuất bản** (không có căn cứ): lời chứng thực mẫu, dải số liệu “100% / 24/7 / A+”, “Trusted by”, logo khách giả,
  thư viện ảnh “A Look at Our Work”, quy trình cố định, giờ làm việc do AI đặt, email/form khi chưa xác minh. Mỗi chỗ vá có ghi chú `QLBM:`.
- Website: chỉ dòng có miền ở B và C trống. Document root đọc từ cPanel, upload không ghi đè.
  C chỉ ghi khi https://B trả 200, chứng chỉ hợp lệ, đúng nội dung, và ô C vẫn trống lúc ghi.

## Chờ chủ dự án chốt

1. **Duyệt bật ghi bản ghi A qua iNET** (theo `PATCH /record` ACTION_ADD, chỉ thêm, không sửa/xoá bản ghi có sẵn).
2. Quy tắc tên miền phụ: bỏ hậu tố pháp lý (app cũ, đang dùng) hay dùng nguyên cột E / rút gọn 2 từ.
3. `th-ntp.com` của app cũ thuộc nick nào.
4. Hạn mức miền / ngày mỗi nick (hiện không giới hạn).
