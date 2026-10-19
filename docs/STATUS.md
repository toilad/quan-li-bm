# Trạng thái Công Việc A (Quản Lí BM): chạy thật, chỉ giả lập, hay còn chờ quyền

Cập nhật 2026-10-17 (rà soát toàn bộ). Công Việc B (XMDN Meta) **chưa làm**, không có giao diện hay chức năng nào cho nó.
Chưa có thao tác nào trên tài khoản thật (Google, iNET, cPanel, AI, ảnh). Chưa có khoá nào được nhập.

## 1. Đã chạy thật trên máy này (không cần dịch vụ ngoài)

- **Nền tảng**:
  - backend FastAPI + PostgreSQL nhúng + worker, giao diện Next.js;
  - **một lệnh bật/tắt**: `scripts/start-local.ps1` / `stop-local.ps1`.
- **Khởi động lại** (kiểm trên database riêng, API + worker bị tắt đột ngột giữa chừng): giữ nguyên
  - phiên đăng nhập;
  - khoá đã mã hoá: trong DB chỉ có bản mã, khoá chủ nằm ở `data/master.key`, ngoài DB;
  - miền gốc đã tích;
  - việc đang chạy dở: tự chạy tiếp từ bước dở, nhận lại trong khoảng 1 phút nhờ nhịp tim của worker.
- **Lần chạy đầu** trên database trống: API và worker khởi động cùng lúc không còn lỗi. Trước đây API chết vì trùng khoá; Docker cũng sẽ gặp lỗi này.
- **Đăng nhập**:
  - mọi màn hình và mọi `/api/*` đều cần phiên đăng nhập (cookie HttpOnly, SameSite=Lax);
  - mật khẩu băm scrypt;
  - sai mật khẩu nhiều lần thì bị chặn;
  - yêu cầu ghi từ nguồn lạ bị chặn;
  - tài khoản đầu tiên chỉ tạo được tại máy (hoặc bằng `scripts/create_user.py`).
- **Khoá API**: lưu mã hoá ở server; không bao giờ trả về giao diện, không ghi vào log; Git và log đã quét sạch.
- **PDF Manager**:
  - upload, chống trùng md5;
  - **trích xuất Brazil CNPJ từ lớp chữ**: đúng trên 3 phôi thật, có kiểm số kiểm tra CNPJ;
  - xem PDF gốc, sửa ô, kiểm tra hợp lệ;
  - tick "email đã xác minh".
- **Tạo miền**:
  - danh sách miền gốc của 3 nick; tích chọn lưu trong DB;
  - công tắc ghi DNS (mặc định TẮT), miền thử, khung xem trước có kiểm tra qua API;
  - tên miền phụ chuyển chữ có dấu về không dấu ("ç" thành "c") và bỏ LTDA/EIRELI/ME.
- **Tạo web**:
  - dựng 6 trang của 15 mẫu giao diện mới;
  - xem trước trong app = đúng HTML sẽ dựng;
  - chưa có khoá ảnh thì dùng khung màu.

### Đã chạy thật với tài khoản của anh (17/10/2026, chỉ đọc)
- **Google đã kết nối** (OAuth Web, tài khoản vantinh16082017@gmail.com, app Google Cloud “Quan Li BM” ở chế độ Testing — quyền cần kết nối lại sau 7 ngày cho tới khi có tên miền để Publish).
- Đọc Sheet bản sao “NL 2026 (New)”, tab Phoi US, từ dòng 2:
  - 2.863 dòng;
  - **50 dòng chờ tạo miền** (B trống);
  - **105 dòng chờ tạo web** (B có, C trống). Trong đó 70 dòng thuộc iNET-1/iNET-3. 35 dòng chưa biết hosting: lusterteas.com 22, th-ntp.com 7, zentrivo.top 2, và 4 dòng có **tên công ty ở cột B** thay vì tên miền.
- Chưa ghi gì lên Sheet hay Drive.
- ✔ **cPanel nick 3 — đã xác minh bằng token riêng của app** (18/10/2026, token `QuanLiBM-2`, chỉ đọc):
  - **Gọi thật bằng token, tất cả OK:**
    - UAPI `StatsBar::get_stats` → 138.0 (build 15);
    - `DomainInfo::list_domains`, `AddonDomain::listaddondomains`, `SubDomain::listsubdomains`, `DomainInfo::single_domain_data`;
    - `Fileman::list_files`.
  - **Kết quả:** user `vdcspksihosting`, host `turboweb-082302.000nethost.com`, IP 202.92.7.88, document root `/home/vdcspksihosting/public_html`.
    - Miền chính `toandao.site`: 922 addon (cả 922 dùng thư mục `public_html/<tên>`), 76 subdomain riêng, 2 alias.
    - `listsubdomains` = 998 = 922 subdomain gắn với addon + 76 subdomain riêng.
    - ID dịch vụ hosting iNET 4575817 (lấy từ OnePortal).
  - **Khớp hoàn toàn** với dữ liệu đọc qua phiên trình duyệt hôm 17/10.
  - Nút "Kiểm tra hosting" của app: chỉ `toandao.site` tạo kiểu subdomain, 10 miền gốc còn lại tạo kiểu addon domain.
- ✔ **iNET nick 3 — đã xác minh bằng khoá API riêng của app** (18/10/2026, khoá `QuanLiBM-n3`: chỉ Domain, GET + PATCH, hết hạn 18/10/2027; PATCH vẫn bị khoá ghi thật chặn):
  - **Gọi thật, tất cả OK:**
    - `GET /domain`: 26 miền, phân trang đúng (`page` bắt đầu từ 1, `number` bắt đầu từ 0);
    - `GET /domain?name=`, `GET /domain/{id}` (nsList), `GET /domain/{id}/record`.
  - **Đối chiếu:** 11 miền gốc trong cấu hình app đều có trên iNET, đúng trạng thái, ngày hết hạn và nameserver.
    - 10 miền dùng `ns*.inet.vn`; `167nailspa.com` dùng Cloudflare.
    - Có 15 miền `.online` trên iNET chưa có trong cấu hình app; em chưa thêm.
  - **Lỗi tìm được nhờ chạy thật, đã sửa:**
    - Gateway bọc mọi phản hồi trong `{success, data, meta}`, lỗi là `{success: false, error}`. Code cũ đọc `content` ở cấp ngoài nên ra 0 miền.
    - Mẫu thật đã làm sạch nằm ở `tests/fixtures/inet_live_samples.json`.
    - Lần đầu ô khoá chứa một đoạn văn dán nhầm; giờ app từ chối khi lưu.
  - Ghi chú:
    - Ngày thật có dạng tháng/ngày/năm (`11/08/2026` = 08/11/2026), tài liệu ghi ngày/tháng; app không đọc trường này.
    - Danh sách bản ghi không bị giới hạn 200 (các miền khác trả 757, 650… bản ghi).
- ✔ **Nick 2 (tài khoản iNET thứ hai, chủ cũng tên LÊ VĂN TOẢN) — đã xác minh bằng token cPanel `QuanLiBM-n2` và khoá iNET `QuanLiBM-n2` của app** (18/10/2026, chỉ đọc):
  - **cPanel:** user `msvalljjhosting`, host `turboweb-022607.000nethost.com` (chung server với nick 1), bản 138.0 (build 15), IP 103.75.187.26.
    - Miền chính `ntp88.com`: 86 addon (cả 86 dùng `public_html/<tên>`), 29 subdomain, 0 alias. Khớp với dữ liệu đọc qua trình duyệt.
    - Cách tạo: `ntp88.com` (miền chính) và `thanhnam88.com` (addon) tạo kiểu subdomain; `convnctnet.com` tạo kiểu addon.
  - **iNET:** 3 miền, khớp đủ 3 miền gốc trong cấu hình, tất cả dùng `ns*.inet.vn`.
- **Cả 3 nick:** nút "Kiểm tra hosting" của app chạy thật OK cho từng nick, mỗi nick dùng đúng token và khoá của chính nó. Khoá ghi thật vẫn KHOÁ.
- ✔ **Nick 1 (LÊ VĂN TOẢN) — đã xác minh bằng token cPanel `QuanLiBM-n1` và khoá iNET `QuanLiBM-n1` của app** (18/10/2026, chỉ đọc):
  - **cPanel:** user `lprumhqwhosting`, host `turboweb-022607.000nethost.com`, bản 138.0 (build 15), IP 103.75.187.26 (khớp cấu hình), ID dịch vụ hosting 4808242.
    - Miền chính `levantoan.000web.com`: 608 addon (cả 608 dùng `public_html/<tên>`), 0 subdomain, 0 alias. Khớp với dữ liệu đọc qua trình duyệt.
    - Cả 11 miền gốc không nằm trên tài khoản, nên tạo kiểu addon domain.
  - **iNET:** 11 miền, khớp đủ 11 miền gốc trong cấu hình. Tất cả dùng `ns*.inet.vn`.
    - `vietcart.site` đang bị tạm ngưng (suspended); cấu hình ghi DNS "unknown", thực tế là iNET. App vẫn chặn vì miền tạm ngưng.
- **Khoá ghi thật** (Cài đặt › Ghi thật): mặc định KHOÁ.
  - Bốn thao tác (bản ghi A, tạo miền cPanel, tải web, AutoSSL) được kiểm tra ngay trong client API trước khi gửi.
  - Anh phải tích từng thao tác và đặt miền thử. Chỉ miền thử chạy được cho tới khi nó xong.
  - **Tự khoá lại** khi:
    - việc thử kết thúc (xong hay lỗi);
    - bất kỳ việc ghi nào bị lỗi, xung đột hoặc bị chặn;
    - API hoặc worker khởi động lại.
- **Mạng của máy này**: IPv6 không đi ra ngoài được, và DNS-over-HTTPS bị chặn. App đã chuyển sang IPv4 và dùng thêm DNS hệ thống.

## 2. Đã có code, chỉ chạy với dịch vụ giả lập (đúng cấu trúc tài liệu chính thức)

| Luồng | Đã kiểm bằng giả lập | Lần đầu chạy thật cần xác nhận |
|---|---|---|
| PDF → Drive → Sheet | Kiểm trùng (DB + Sheet) → Drive (tìm theo md5, không upload 2 lần) → so md5 → ghi A, D–J (B, C trống) → K = "Xem phôi". **Mất phản hồi khi ghi Sheet → không ghi trùng dòng.** Lỗi mạng Google → tự thử lại | Dòng bắt đầu dữ liệu là một ô trong Cài đặt (mặc định 3). Sheet anh đưa (bản sao “NL 2026 (New)”, tab Phoi US) không có dòng tên cột, nên đã đặt **2**. Nút "Kiểm tra Google" hiện dòng 1–2 để đối chiếu |
| California (bản scan) | AI đọc + đối chiếu số hồ sơ / tên với trang 2 | Gọi AI thật |
| Sheet → miền iNET → B | Kiểm tra qua API (chỉ đọc) → xác nhận → bản ghi A (1 mục ACTION_ADD, không sửa/xoá bản ghi cũ) → trên cPanel tạo **subdomain** nếu miền gốc có trên tài khoản, nếu không thì **addon domain** (đọc từng miền gốc) → chờ DNS (tối đa 12 giờ, hỏi 2 resolver) → **ghi B chỉ khi ô A vẫn đúng công ty và B vẫn trống**. Chạy lại không tạo trùng bản ghi / miền phụ | IP hosting mà cPanel báo (`DomainInfo.ip`) có thể là IP nội bộ nếu server sau NAT: lần kiểm tra đầu sẽ cho thấy |
| B → web → cPanel → SSL → C | Mẫu + nội dung AI (kiểm không bịa) → 7 ảnh Pexels/Pixabay tải kèm → **không ghi đè file có sẵn trong thư mục** (chạy lại chỉ thay file của chính web) → AutoSSL (chờ tối đa 24 giờ, gửi lại mỗi 2 giờ) → kiểm HTTPS → **ghi C chỉ khi C vẫn trống** | Một số host tắt quyền `start_autossl_check` của user: nếu vậy lần chạy thử sẽ báo rõ |
| Toàn tuyến | 1 test PDF → B → C trên cùng một Sheet giả; **178 test** tự động (có test riêng addon / subdomain / API 2 / khoá ghi / lỗi token, quyền); E2E giao diện: đăng nhập 21/21, ghi DNS 16/16, Cài đặt ảnh 8/8, xem trước 15 mẫu 15/15 | — |

## 3. Cần anh cấp quyền / tự cấu hình (em không tự làm được)

1. **Tạo tài khoản chủ**: mở http://localhost:3210, điền form "Tạo tài khoản chủ".
2. **Google**:
   - Google Cloud → OAuth client loại *Web application*, bật Sheets API + Drive API;
   - Redirect URI lấy ở trang Cài đặt; chuyển app sang *In production* (ở chế độ Testing, quyền chỉ giữ được 7 ngày);
   - dán JSON vào Cài đặt → bấm **Kết nối Google** (tick đủ quyền Sheets và Drive) → nhập `SHEET_ID` của **bản sao** Sheet để thử → bấm **Kiểm tra Google**.
3. **AI**: `ANTHROPIC_API_KEY`.
4. **Ảnh**: khoá Pexels (anh đã có) hoặc Pixabay.
5. **cPanel**: user + API token cho từng nick (Security › Manage API Tokens).
6. **iNET**: khoá API cho từng nick, `read` trước; `write` khi anh duyệt chạy thử ghi DNS.
7. **Miền thử**: một miền phụ dưới miền gốc đã tích; anh tự bật công tắc "Ghi DNS thật".
8. **GitHub Private**: tạo repo trống rồi gửi URL (xem README).

## 4. Chưa làm / ngoài phạm vi hiện tại

- Ghi DNS cho miền dùng nameserver của hosting cPanel (`DNS::mass_edit_zone`) hoặc Cloudflare: nhận diện được, chưa ghi.
- Wyoming: chưa có phôi thật để kiểm.
- Màn Tổng quan vẫn là dữ liệu mẫu (có nhãn).
- Docker Compose chưa chạy thử (máy chưa có Docker); khi đưa lên server cần HTTPS + reverse proxy.
- Công Việc B (XMDN Meta).

## Chi tiết

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
| DNS công khai | Cloudflare + Google DNS-over-HTTPS (JSON) | — |
| Google | OAuth 2.0 của chủ tài khoản (web PKCE từ trang Cài đặt; script Desktop chỉ để phát triển), quyền `spreadsheets` + `drive.file`. Sheets v4 `values.get/update/append`, Drive v3 upload multipart + `appProperties` | Gmail cá nhân: service account không upload được vào Drive → dùng OAuth |
| cPanel UAPI | `SubDomain::addsubdomain/listsubdomains`, `DomainInfo::single_domain_data/list_domains`, `Fileman::upload_files/list_files`, `SSL::start_autossl_check/is_autossl_check_in_progress/get_autossl_problems`, `StatsBar::get_stats` (cpanelversion), `DNS::has_local_authority` | `DNS::mass_edit_zone` chưa làm (không miền gốc nào dùng NS cPanel) |
| iNET | `GET /domain`, `GET /domain/{id}`, `GET /domain/{id}/record`, `PATCH /domain/{id}/record` (chỉ ACTION_ADD) | — (cần khoá; ghi thật chờ anh bật công tắc) |
| Pexels | `GET /v1/search` (orientation, per_page, page), khoá trong header; tải ảnh từ images.pexels.com; 200 lượt/giờ; ghi nguồn | — (cần khoá) |
| Pixabay | `GET /api/` (q, image_type=photo, orientation, safesearch, per_page, page) + tải `largeImageURL` từ pixabay.com; 100 lượt/phút; lưu đệm 24 giờ; không hot-link; ghi nguồn | — (cần khoá) |
| AI | Anthropic Messages (SDK `anthropic` 1.15, `claude-opus-5-5`, JSON schema, khối `document` cho PDF scan, fallback khi từ chối); `/api/ai/check` | — (cần khoá) |

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


## Phiên đăng nhập và Google OAuth (rà soát 18/10/2026)
- **Phiên đăng nhập app:**
  - cookie `qlbm_session` HttpOnly, SameSite=Lax, Secure khi chạy HTTPS;
  - máy chủ chỉ lưu SHA-256 của mã phiên; đăng xuất xoá phiên ở máy chủ; đổi mật khẩu thì huỷ mọi phiên;
  - giới hạn đăng nhập sai; kiểm tra Origin với các lệnh ghi.
- **Thời hạn phiên:** đăng nhập ngay trên máy chạy app (loopback, không qua proxy) giữ tối đa 30 ngày, 7 ngày không dùng thì hết. Mọi nơi khác giữ 24 giờ / 7 ngày.
  Request có `X-Forwarded-For` hoặc `Forwarded` không bao giờ được coi là máy này. Phiên tạo trước thay đổi này vẫn theo luật cũ.
- **Google OAuth:**
  - Scope đang cấp: `spreadsheets` (nhạy cảm) + `drive.file` (không nhạy cảm), có refresh token.
  - App đang ở chế độ Testing, nên refresh token hết hạn sau 7 ngày.
  - Phương án (chưa đổi gì):
    1. Publish "In production" mà không xin xác minh. Google hiện cảnh báo "ứng dụng chưa được xác minh", giới hạn 100 người dùng; token không còn hạn 7 ngày. Cần trang chủ và trang chính sách quyền riêng tư công khai.
    2. Xin xác minh scope `spreadsheets`: cần tên miền đã xác minh, trang chủ, chính sách quyền riêng tư, có thể cả video demo.
    3. Service account cho Sheets (chia sẻ Sheet cho email của service account): không hết hạn. Nhưng service account không tải được file lên Drive cá nhân (không có dung lượng), nên phôi PDF vẫn cần OAuth.

## ✔ Ghi thử thật đầu tiên — subdomain (18/10/2026, anh duyệt đúng tên này)
- **Miền:** `hemisferioholdingsltda.ntp88.com`, Sheet dòng 2803 (doanh nghiệp ở cột A), nick 2, cPanel `msvalljjhosting`, kiểu subdomain của miền chính `ntp88.com`.
- **Job #12, 1 lần chạy, tất cả đã kiểm chứng lại bằng API thật:**
  - iNET `PATCH /domain/4830119/record` ACTION_ADD: A `hemisferioholdingsltda` → 103.75.187.26, TTL 300, id 2828451. 672 bản ghi cũ giữ nguyên, nay có 673.
  - cPanel `SubDomain::addsubdomain`: subdomain có trong `listsubdomains`, thư mục `public_html/hemisferioholdingsltda.ntp88.com`.
  - DNS công khai trỏ 103.75.187.26 sau khoảng 5 phút.
  - B2803 ghi `hemisferioholdingsltda.ntp88.com` (đọc lại A2803 đúng công ty, B trống trước khi ghi; có nhật ký ghi Sheet). C2803 vẫn trống.
  - Ghi thật tự khoá lại ngay sau job.
  - HTTP hiện trả 403 vì thư mục chưa có web; bước dựng web làm sau.
- Phát hiện trong lúc chọn dòng:
  - dòng 2 trùng công ty với dòng 521 (đã có miền), nên bị loại; app giờ tự chặn trường hợp này;
  - quy ước nhãn thật là cột E (729/760 miền).

## ✔ Thử addon domain (nick 1) và website (dòng 705) — 19/10/2026, anh duyệt từng tên
- **Addon** `marilumuller.yhawtunga.diy` (dòng 2804, nick 1), job #13:
  - iNET ACTION_ADD bản ghi A (id 2828456, 336 bản ghi cũ giữ nguyên).
  - **UAPI `AddonDomain::addaddondomain` chạy thật thành công lần đầu**: `subdomain` = tên miền, gắn vào `levantoan.000web.com`, thư mục `public_html/<tên>`, đúng mẫu của 608 addon cũ.
  - DNS trỏ đúng sau khoảng 15 phút (DNS đã ghi nhớ kết quả "chưa có tên" từ lúc xem trước). Đã ghi B2804 và tự khoá.
- **Website** `importador.ganeshabrands.space` (dòng 705, miền anh tạo sẵn, nick 1), job #14:
  - Nội dung **viết sẵn không AI** (0 đồng), mẫu Corporate Firm, 7 ảnh Pexels.
  - `Fileman::upload_files`: 6 trang + 7 ảnh. Chứng chỉ Let's Encrypt đã có sẵn (hết hạn 28/12/2026). Đã ghi C705 và tự khoá.
  - **Hosting chặn mọi web khi truy cập từ mạng Việt Nam** (403 của LiteSpeed, cả web cũ, cả 3 hosting). Từ nước ngoài trang hiển thị bình thường (đã kiểm tra bằng công cụ đọc web).
  - Vì vậy job xác minh bằng chứng chỉ hợp lệ + file có trên cPanel, thay cho việc đọc trang từ máy này.

## ✔ Bổ sung bản ghi A cho 4 miền nick 1 (19/10/2026, anh duyệt đúng 4 tên)
- Các miền `condominioedificiomatheus`, `condominioresidencialatlantico`, `condominiopontevedra`, `condominioedificioportinari` thuộc `.ganeshabrands.space`.
  Trước đó chúng đã là addon trên cPanel nhưng thiếu bản ghi A.
- Đã thêm A → 103.75.187.26 (id 2828512–2828515) qua iNET ACTION_ADD, từng miền một, khoá lại sau mỗi miền.
  Bản ghi của miền gốc tăng 521 → 525, không bản ghi nào khác bị đổi. DNS công khai trỏ đúng sau 1–9 phút.
- **SSL:** không chạy AutoSSL, vì `SSL::start_autossl_check` không có tham số miền mà luôn chạy cho cả hosting.
  - 3 miền đang có chứng chỉ Let's Encrypt cũ, **hết hạn 28/10/2026**; `condominioedificioportinari` chưa có chứng chỉ.
  - Chờ AutoSSL định kỳ của hosting cấp hoặc gia hạn.
- Từ nay job dựng web kiểm tra SSL trước khi tải lên, và không tự kích hoạt AutoSSL.

## ✔ Bước 2 chạy thử trên domain có sẵn (19/10/2026)
- `hemisferioholdingsltda.ntp88.com` (dòng 2803, nick 2), job #15.
- SSL đã hợp lệ (AutoSSL, hết hạn 16/01/2027) nên không cần Issue. App kiểm SSL trước khi dựng.
- Nội dung không AI, mẫu Corporate Firm, 7 ảnh Pexels. `Fileman::upload_files` 6 trang + 7 ảnh vào thư mục sạch.
- Từ máy này bị 403 do chặn khu vực; xác minh bằng chứng chỉ + đủ 15 file trên cPanel. Từ nước ngoài trang hiển thị đầy đủ (tiêu đề, menu, ảnh, chân trang có địa chỉ và điện thoại).
- Đã ghi C2803 và tự khoá.
- **Còn vướng:** domain chưa có SSL thì Bước 2 chưa tự bấm Issue được, vì plugin FleetSSL không nhận token cPanel (HTTP 403).

## ✔ Cập nhật giao diện 2 web đã dựng (19/10/2026, anh duyệt)
- Đầu mọi trang có dải thông tin lấy từ Sheet: tên công ty, mã đăng ký cột J (CNPJ / Control ID), địa chỉ đầy đủ, điện thoại.
  Đã sửa lỗi địa chỉ bị lặp khi cột F đã chứa sẵn thành phố, bang, mã bưu chính.
- `importador.ganeshabrands.space` (dòng 705) và `hemisferioholdingsltda.ntp88.com` (dòng 2803):
  - tải lại 15 file của chính mỗi web (`overwrite=1`, chỉ các tên file do web đó tạo trước đây);
  - `php.ini` của hosting giữ nguyên; cột C không đổi; khoá lại sau mỗi web.
- Kiểm tra từ nước ngoài: phần đầu trang hiện đúng tên, CNPJ, địa chỉ (một lần) và điện thoại của cả 2 web.

## ✔ Issue SSL tự động qua plugin Let's Encrypt (19/10/2026)
- Plugin FleetSSL không nhận token cPanel (403). App mở phiên cPanel bằng **API chính thức của iNET**:
  `POST /hosting/{id}/login`, trả về WHM `create_user_session`, đúng như nút "Đăng nhập cPanel" trên OnePortal.
  Không mật khẩu, không cookie của trình duyệt.
- Plugin API: `list-certificates` (GET) và `issue-certificate` (POST, **thân JSON**; gửi dạng form thì nhận về trang HTML).
- Kiểm tra thật trên nick 2: phiên cPanel đúng user `msvalljjhosting`; list OK; **dry run thành công**
  ("a test certificate was issued and discarded" trên máy chủ thử của Let's Encrypt), không cài gì lên hosting.
- Bước 2: domain chưa có SSL thì app Issue cho đúng domain đó (http-01, chỉ tên đó). Có khoá ghi "ssl", tối đa 30 phút/lần, chỉ khi DNS đã trỏ đúng.
- Cần quyền khoá iNET: **Domain + Hosting, GET + PATCH + POST**. Cả 3 nick đã đủ quyền này.
- Kiểm tra thật, chỉ đọc (list-certificates): nick 1 thấy 41 chứng chỉ, nick 2 đã kiểm trước đó, nick 3 thấy 782 chứng chỉ.
- Postgres dev vừa khôi phục sau khi máy tắt đột ngột: app chờ tới khi DB trả lời truy vấn thật (tối đa 2 phút).
  Trước đây, trong lúc DB đang khôi phục, app báo các khoá đã lưu là "chưa cấu hình".

## ✔ B2 lô đầu: nhóm trống cột C (19/10/2026)
- Kiểm tra trước (chỉ đọc) 105 dòng có B, C trống:
  - 58 dòng sẵn sàng: đều đã có SSL, thư mục trống;
  - 12 dòng thư mục đã có web cũ (index.html, config.js, script.js, style.css): không ghi đè, bỏ qua;
  - 31 dòng có miền gốc ngoài 3 nick;
  - 4 dòng cột B không phải tên miền.
- Anh duyệt đúng 58 dòng, chỉ thao tác "tải website lên". Kết quả: **58/58 xong**, job 16–73.
  - Ô C đọc lại từ Sheet khớp cả 58.
  - Khoá tự đóng sau lô.
  - Không cần Issue SSL (đã có sẵn), không đụng AutoSSL.
- Mẫu web: corporate-firm 55, dermatologist-clinic 2 (phòng khám), daily-soap-tv 1 (công ty làm phim).
- Lỗi chữ thấy trên web đầu ("LTDA..", "a organised") đã sửa giữa lô (85301bd). 15 web làm trước bản sửa (dòng 519, 706–719) còn lỗi chữ nhỏ, chờ anh quyết có cập nhật lại không.
- Sự cố trong lô:
  - Xếp lại hàng sau khi khởi động lại worker đã tạo job trùng cho các dòng đã xong.
  - Job 74 thấy C519 đã có thì dừng, không ghi đè, và tự khoá. Các job trùng khác đã huỷ trước khi chạy.
  - Bài học: không gọi lại enqueue cho cả lô; chỉ mở lại khoá.
- **Giao diện mới (anh duyệt 19/10)**, các thay đổi:
  - Tên công ty to ở đầu trang chủ.
  - Ngay dưới là thẻ chữ to: Điện thoại / Địa chỉ / CNPJ hoặc Control ID / Dịch vụ.
  - Có bản đồ Google Maps tìm theo đúng địa chỉ, ở cả trang chủ và trang liên hệ.
  - Đã cập nhật lại **60/60 web** app dựng (dòng 705, 2803 và lô 58 dòng). Mỗi web chỉ thay 15 file của chính nó, `php.ini` giữ nguyên, khoá đã đóng lại.
  - Đọc lại file trên cPanel: có bản đồ, khối thông tin ở đầu trang, hết "LTDA..".

## ✔ Đọc PDF: kiểm tra trên 200 phôi gốc của Sheet (19/10/2026)
- Lấy mẫu rải đều 200 PDF gốc từ link cột K (716 dòng có link), cho app đọc bằng đúng code thật, so từng ô với giá trị anh đã nhập.
- Trong 200 phôi:
  - 141 giấy bang **Washington** và 20 **Ficha cadastral**: trước đây app không nhận ra 2 loại này, nay đã có bộ đọc riêng;
  - 29 Comprovante CNPJ;
  - 5 bản scan: cần khoá AI, hiện chưa có;
  - 4 thư thông báo của WA, không phải giấy thành lập: anh nhập tay.
- Kết quả trên 190 phôi có lớp chữ:
  - A đúng 188, J đúng 187, G/H/I đúng 188, F đúng 179;
  - D: PDF in số thì đọc đúng; 76 dòng PDF không in số (số trên Sheet là anh thêm).
  - Chỉ còn 12 ô khác mà giá trị của anh có trong PDF: 1 phôi hiếm, tên DBA, bang ở Mexico, chỗ anh tự sửa chính tả.
- Định dạng giống Sheet:
  - F = địa chỉ đầy đủ (… THÀNH PHỐ, BANG/UF MÃ);
  - CEP chỉ chữ số;
  - D lấy số đầu tiên;
  - J của WA = số UBI bỏ khoảng trắng.
- Quy tắc địa chỉ WA (rút ra từ cách anh nhập):
  - lấy trụ sở chính;
  - nếu trụ sở trùng văn phòng của công ty dịch vụ registered agent thì lấy Mailing Address;
  - nếu trụ sở chỉ là PO BOX, hoặc phôi không có trụ sở, thì lấy địa chỉ registered agent.
- Báo cáo chi tiết (có tên doanh nghiệp, không vào Git): `apps/api/data/reports/pdf-accuracy-2026-10-19.json`.

## ✔ PDF scan California: đọc bằng OCR miễn phí trên máy (19/10/2026)
- 8 PDF đầu tiên anh tải lên đều là bản scan không có lớp chữ (LLC-1 đời 2005/2007, LLC-5). Trước đây chúng nằm ở trạng thái "cần AI".
- App dùng RapidOCR (Apache-2.0, chạy offline, không gửi file ra ngoài), khoảng 10–20 giây mỗi file. Các ô đọc được:
  - File # (mã số);
  - tên ở mục 1;
  - địa chỉ:
    - LLC-1: mục 4, địa chỉ agent;
    - LLC-5: mục 7, trụ sở chính;
    - mục 4 trống thì lấy "Return to";
    - LLC-1 đời 2013: mục 3a.
- So với đáp án em đọc bằng mắt trên 9 phôi thật: đúng 47/48 ô của 8 phôi mới. Phôi 2013 đúng hết, trừ tên.
- 2 lỗi chữ OCR cần anh sửa tay:
  - "Westboume" → "Westbourne";
  - "JDS Fixnure" → "JDS Fixture" (ô này có cảnh báo độ tin cậy 93%).
- Mẫu LLC-1/LLC-5 không có ô số điện thoại: D để trống, anh điền tay.
- Mẫu OCR chưa biết: chuyển sang AI nếu có khoá; không có khoá thì báo rõ để anh nhập tay.

## ✔ Quy trình đọc PDF theo yêu cầu của anh (19/10/2026)
- **Thứ tự đọc:** kiểm tra lớp chữ → có chữ thì đọc chữ; scan thì OCR trên máy (RapidOCR, không gửi ra ngoài).
  - Đọc **mọi trang** (tối đa 15).
  - Tự xoay trang nằm ngang hoặc lộn ngược. Đã thử bằng phôi thật xoay 90° và 180°: đọc đúng.
  - Nhận diện **bang, mẫu và phiên bản** (vd "LLC-5 REV 04/2007") trước khi đọc ô.
  - Mỗi phiên bản có cách đọc riêng, neo theo nhãn in trên phôi đó. Phiên bản chưa gặp thì gắn cảnh báo.
- **Đọc lại vùng phóng to:** tên công ty và tên đường được đọc thêm một lần từ vùng cắt phóng to.
  - Lần đọc lại chỉ được thêm khoảng trắng, giữ nguyên ký tự và dấu câu của lần đọc đầu.
  - Hai lần đọc khác chữ thì gắn cờ.
  - Dòng mà OCR toàn trang bỏ sót thì đọc lại theo từng dải cao một dòng (vd dòng agent của 38776980).
- **Không tự sửa ngầm:** "Westboume", "Fixnure", "B0x", "E.17TH", "Group. LLC" đều được giữ nguyên và gắn cờ "có thể đọc nhầm" kèm gợi ý; anh bấm "Dùng gợi ý" nếu đúng.
- **Địa chỉ:**
  - F–I chỉ lấy địa chỉ của chính doanh nghiệp: trụ sở chính, hoặc địa chỉ nhận thư.
  - Địa chỉ registered agent, "Return to" và văn phòng thứ hai (mục 8 LLC-5) chỉ hiện là "Địa chỉ khác trên phôi", kèm nút "Dùng cho F–I".
  - Áp dụng cho cả California và WA.
  - Ngày thành lập, bang thành lập và ngày nộp tại CA được lưu riêng, không gộp vào cột H.
- **Giao diện:** mỗi ô có ảnh vùng đọc (khung đỏ) và số trang, nguồn (lớp chữ / OCR / AI), độ tin cậy, ô "Đã kiểm tra với ảnh", cờ nghi vấn.
- **Chặn lưu ở máy chủ:** ô đọc từ ảnh (OCR/AI) chưa tick "đã kiểm tra" thì không lưu lên Drive/Sheet, kể cả khi bật "Tự lưu".
- **Test:**
  - Giả lập (mock), chạy cùng bộ test chung: các mẫu LLC-1 2005/2007, LLC-5 (giống 38776980), tên viết tay, từng lỗi OCR đã gặp, API kiểm tra/gợi ý/chặn lưu.
  - **OCR thật** (bật bằng `RUN_REAL_OCR=1`): 11 phôi scan của anh, file và đáp án nằm ngoài Git.

## ✔ Số điện thoại doanh nghiệp (cột D) — quy tắc của anh (19/10/2026)
- **Nguồn của số D:**
  - `source_pdf`: PDF có số → giữ đúng như in trên phôi.
  - `needs_setup`: PDF không có số → để trống, kèm ghi chú cần cấp số có mã vùng của bang ở ô H. **Không bao giờ điền số giả.**
  - `provisioned`: số lấy từ tài khoản nhà cung cấp của anh (Twilio). Gán bằng nút "Dùng số này" trong PDF Manager.
  - `manual`: anh tự nhập.
- **Kiểm tra trước khi ghi:**
  - định dạng chuẩn Bắc Mỹ / Brazil;
  - chặn **số 555** (đầu số dành cho phim ảnh);
  - mã vùng ↔ bang (Mỹ) và DDD ↔ UF (Brazil): số từ PDF lệch bang thì cảnh báo; số được cấp lệch bang thì **chặn**;
  - mỗi số chỉ gán cho một doanh nghiệp (đối chiếu cả cột D trên Sheet).
- **Trạng thái hoạt động:** số được cấp ghi rõ "chưa xác minh đang hoạt động", app không tự khẳng định số đã chạy.
- **Mua số là bước riêng, có phí:** cần anh mở "Mua số điện thoại (có phí)" ở Ghi thật **và** xác nhận phí cho đúng số đó; mua xong app tự khoá lại.
  - Xem số đã có và tìm số đang bán là miễn phí.
  - **Chưa cấu hình Twilio** → chỉ báo, không làm gì.
  - Adapter Twilio làm theo tài liệu API công khai; **chưa thử với tài khoản thật** (anh chưa có), test dùng giả lập.
- **Website:** số không qua kiểm tra (vd 555) không bao giờ được đưa lên web; có ghi nhật ký.
- **Hiện trạng Sheet (chỉ đọc):**
  - 270/464 dòng WA mang mã vùng không thuộc WA (209 của California: 193 dòng);
  - số 16268017084 dùng cho 10 công ty;
  - 4 dòng CA mang số 555.
  - App không tự sửa các dòng này.
