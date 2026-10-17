# Trạng thái: chạy thật, mô phỏng hay còn thiếu

Cập nhật 2026-10-17. Đã có backend thật (FastAPI + PostgreSQL + worker). Giao diện gọi backend thật;
dịch vụ nào chưa cấu hình / chưa khả dụng thì màn hình **ghi rõ**, không báo thành công giả.
Chưa thao tác lên tài khoản thật nào (chưa có khoá). Mọi dịch vụ ngoài trong kiểm thử đều là mock.

## Từng chức năng

| Chức năng | Chạy thật (đã kiểm) | Có code, chờ cấu hình để chạy thật | Chưa khả dụng / còn thiếu |
|---|---|---|---|
| PDF Manager | Upload lên server, chống trùng md5, **nhận diện + trích xuất Brazil CNPJ từ lớp chữ** (đúng trên 3 phôi thật, kiểm số kiểm tra CNPJ), xem PDF gốc, sửa ô, kiểm tra hợp lệ ở server. **Luồng lưu chạy xuyên suốt giao diện → API → worker → PostgreSQL** với Google giả lập: kiểm trùng (DB + Sheet) → Drive (tìm theo md5 trước, không upload 2 lần) → md5 → Drive ID → dòng A, D–J (B, C trống) → K = “Xem phôi”; Sheet lỗi → chỉ ghi lại Sheet; tạm dừng/tiếp tục. Ô tick **“email liên hệ chính thức (đã xác minh)”** trên thẻ CNPJ | Ghi Google thật — cần OAuth của anh; bản scan (California): AI nhận diện + đọc ô, **đối chiếu số hồ sơ và tên với bản in lại ở trang sau** (khác số → chặn lưu tới khi anh sửa tay) — cần ANTHROPIC_API_KEY | Wyoming: **chưa có phôi thật để kiểm** |
| Tạo miền | 25 miền gốc của 3 nick, **tích chọn lưu trong database**, kiểm tra nick chỉ đọc (cPanel `DomainInfo::list_domains` + **phiên bản cPanel**; iNET `GET /domain`), chặn miền tạm ngưng / Cloudflare, khoá bỏ chọn miền đang có tác vụ, từ chối dòng gán miền chưa tích. **Tạo bản ghi A qua iNET** (`PATCH /record`, 1 mục ACTION_ADD) chạy xuyên suốt giao diện → API → worker trên iNET/cPanel/Google giả lập: công tắc TẮT mặc định → chạy thử đúng 1 miền anh chỉ định → hàng loạt; mỗi lượt phải **kiểm tra qua API (chỉ đọc) rồi xác nhận** | Mọi bước trên tài khoản thật — cần khoá iNET (`write`), token cPanel, Google; **anh bật công tắc + chỉ định miền thử** | Miền dùng DNS của hosting cPanel (`DNS::mass_edit_zone`) hoặc Cloudflare: nhận diện được, **chưa ghi** |
| SSL + Tạo web | **15 mẫu đổi sang giao diện mới theo trang tham khảo anh chọn (2026-10-17)** (`brand_render.py`): đầu trang gradient + mảng cong + khung ảnh, thẻ thông tin nổi (chỉ dữ kiện thật), khối "Who we are", dải tràn có thẻ thông tin (điện thoại / địa chỉ / dịch vụ / giờ), thẻ dịch vụ gradient, khối liên hệ gradient, chân trang đen. Mỗi mẫu có dải màu + font tiêu đề riêng; chi tiết bố cục đổi theo tên miền. 6 trang + robots/sitemap; xem trước = đúng HTML sẽ dựng. **Email chỉ hiện khi đã xác minh**. Bản đồ = link Google Maps theo đúng địa chỉ, không ghim đoán. **Ảnh từ Pexels API**: mỗi web 7 ảnh chọn theo ngành của mẫu + tên miền (≤ 3 lượt tìm/web), tải về và upload kèm web (`photo-*.jpg`, không hot-link), chân trang ghi “Photos by … on Pexels”; chưa có khoá → khung gradient (loremflickr của app cũ đang lỗi 500 nên đã bỏ). Mẫu cũ khôi phục từ EXE vẫn giữ trong repo (`legacy/`), không còn dùng để dựng | Ảnh thật: cần anh nhập khoá Pexels ở Cài đặt | Quét Sheet (B có, C trống) — cần Google; document root đọc từ cPanel, nội dung AI + kiểm tra không bịa, upload `overwrite=0`, AutoSSL, kiểm HTTPS, đọc lại C rồi ghi — cần token cPanel + ANTHROPIC_API_KEY | — |
| Cài đặt API | Trang **Cài đặt API**: Google, AI, máy chủ, iNET/cPanel × 3 nick. Khoá **mã hoá ở server** (Fernet, khoá chủ `data/master.key` hoặc `QLBM_MASTER_KEY`), không bao giờ trả về giao diện hay ghi log. Nút **Kết nối Google** (OAuth web, PKCE) + kiểm tra Google chỉ đọc | OAuth client loại *Web application* + redirect URI của server | — |
| Tổng quan | Giao diện | — | Vẫn là **dữ liệu mẫu** (có nhãn “Dữ liệu mẫu”) |
| Nền tảng | Hàng đợi PostgreSQL (chống chạy trùng, một việc/nick, thử lại có giãn cách, chạy tiếp từ bước dở, tạm dừng/tiếp tục), nhật ký từng việc, bảng `sheet_writes`, sao lưu/khôi phục `pg_dump`; **khởi động lại API + worker giữ nguyên dữ liệu và việc dở**. **Đăng nhập**: mọi màn hình + mọi `/api/*` cần phiên (cookie HttpOnly), mật khẩu scrypt, chặn sai mật khẩu nhiều lần, chặn yêu cầu ghi từ nguồn lạ; tài khoản đầu tiên tạo tại máy hoặc bằng `scripts/create_user.py` | Docker Compose (db, api, worker, web, backup), cổng chỉ mở trên 127.0.0.1 — **chưa chạy thử** (máy này chưa có Docker) | Chỉ 1 vai trò (chủ); HTTPS + reverse proxy khi đưa lên server; GitHub Private (chưa có remote) |

Kiểm thử: `apps/api` **109 test** (gồm đăng nhập, 15 mẫu web mới × 10 tên miền, ảnh Pexels giả lập), mọi API ngoài đều mock (iNET là tài khoản giả có trạng thái, theo đúng cấu trúc tài liệu).
Gồm **1 test toàn tuyến** trên cùng một Sheet giả: lưu PDF → chạy thử → xem trước → tạo miền (B) → dựng web (C).
E2E giao diện trên backend giả lập (chặn mọi lời gọi ra ngoài): đăng nhập 21/21, ghi DNS (tắt → chạy thử → hàng loạt) 16/16, xem trước 15 mẫu 15/15.
Trên backend dev: các màn 14/14, Cài đặt 11/11, xác minh email 6/6, xem trước 15 mẫu 15/15.

### Ghi DNS thật — các lớp bảo vệ
1. Công tắc **Ghi DNS thật** (Cài đặt) mặc định TẮT. Khi tắt, việc tạo miền dừng ở "Chưa khả dụng" trước mọi thao tác ghi.
2. Bật được chỉ khi đã chỉ định **miền thử** (miền phụ dưới miền gốc đã tích). Chạy thử thì mỗi lượt chỉ được đúng miền đó.
   Miền thử xong trọn vẹn (A + cPanel + DNS trỏ đúng + ghi B) thì mới được chạy hàng loạt.
3. Mỗi lượt: **Kiểm tra qua API (chỉ đọc)** cho từng dòng:
   - miền gốc có trên cPanel và IP hosting (`DomainInfo.ip`) khớp IP của nick;
   - miền nằm trong **đúng tài khoản iNET của nick** (ID miền);
   - nameserver là iNET;
   - bản ghi đang dùng tên đó;
   - DNS công khai.
   Anh xem rồi bấm xác nhận. Lượt chạy chỉ lấy đúng kế hoạch vừa kiểm tra (dùng 1 lần, hạn 30 phút).
4. Khi ghi: kiểm tra lại ID miền và nameserver. Bản ghi giống hệt đã có thì không gửi lại. Tên đã có bản ghi khác thì xung đột, không ghi đè/sửa/xoá.
   Sau PATCH, mọi bản ghi cũ phải còn, nếu không thì dừng.
5. Nhật ký từng việc ghi mọi lời gọi API (phương thức, đường dẫn, thao tác, mã HTTP, không có khoá) và trạng thái từng bước để chạy tiếp khi lỗi.

## API

| Dịch vụ | Đã dùng (theo tài liệu chính thức) | Thiếu |
|---|---|---|
| Google | OAuth 2.0 của chủ tài khoản (web PKCE từ trang Cài đặt; script Desktop chỉ để phát triển), quyền `spreadsheets` + `drive.file`. Sheets v4 `values.get/update/append`, Drive v3 upload multipart + `appProperties` | Gmail cá nhân: service account không upload được vào Drive → dùng OAuth |
| cPanel UAPI | `SubDomain::addsubdomain/listsubdomains`, `DomainInfo::single_domain_data/list_domains`, `Fileman::upload_files`, `SSL::start_autossl_check/is_autossl_check_in_progress/get_autossl_problems`, `StatsBar::get_stats` (cpanelversion), `DNS::has_local_authority` | `DNS::mass_edit_zone` chưa làm (không miền gốc nào dùng NS cPanel) |
| iNET | `GET /domain`, `GET /domain/{id}`, `GET /domain/{id}/record`, `PATCH /domain/{id}/record` (chỉ ACTION_ADD) | — (cần khoá; ghi thật chờ anh bật công tắc) |
| Pexels | `GET /v1/search` (orientation, per_page, page) + tải ảnh từ `images.pexels.com`; giới hạn 200 lượt/giờ, 20.000/tháng; ghi nguồn theo hướng dẫn Pexels | — (cần khoá) |
| AI | Anthropic Messages (SDK `anthropic` 1.15, `claude-opus-5-5`, JSON schema, khối `document` cho PDF scan, fallback khi từ chối); `/api/ai/check` | — (cần khoá) |

## Tối thiểu để kiểm thử thật

1. **Google**: OAuth client loại **Web application** (bật Sheets API + Drive API), redirect URI = `PUBLIC_API_URL/api/google/oauth/callback`
   (trang Cài đặt hiện sẵn). Dán JSON client ở trang Cài đặt → bấm **Kết nối Google**. `SHEET_ID` của **bản sao Sheet để thử**.
2. **AI**: `ANTHROPIC_API_KEY`. **Ảnh web**: khoá Pexels (miễn phí, pexels.com/api) ở Cài đặt › Ảnh cho website.
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
- Những phần **không xuất bản** (không có căn cứ) — ở mẫu cũ lẫn trang tham khảo: số người theo dõi/đăng ký, sao đánh giá, "Verified by", thanh kỹ năng %, nút video không có video, bong bóng like/tim, lời chứng thực mẫu, dải số liệu “100% / 24/7 / A+”, “Trusted by”, logo khách giả,
  thư viện ảnh “A Look at Our Work”, quy trình cố định, giờ làm việc do AI đặt, email/form khi chưa xác minh. Mỗi chỗ vá có ghi chú `QLBM:`.
- Website: chỉ dòng có miền ở B và C trống. Document root đọc từ cPanel, upload không ghi đè.
  C chỉ ghi khi https://B trả 200, chứng chỉ hợp lệ, đúng nội dung, và ô C vẫn trống lúc ghi.

## Chờ chủ dự án chốt

1. **Miền thử** cho lần ghi DNS thật đầu tiên (anh chỉ định, anh tự bật công tắc khi duyệt chạy thử).
2. Quy tắc tên miền phụ: bỏ hậu tố pháp lý (app cũ, đang dùng) hay dùng nguyên cột E / rút gọn 2 từ.
3. `th-ntp.com` của app cũ thuộc nick nào.
4. Hạn mức miền / ngày mỗi nick (hiện không giới hạn).
