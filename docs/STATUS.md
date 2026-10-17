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
- **Mạng của máy này**: IPv6 không đi ra ngoài được, và DNS-over-HTTPS bị chặn. App đã chuyển sang IPv4 và dùng thêm DNS hệ thống.

## 2. Đã có code, chỉ chạy với dịch vụ giả lập (đúng cấu trúc tài liệu chính thức)

| Luồng | Đã kiểm bằng giả lập | Lần đầu chạy thật cần xác nhận |
|---|---|---|
| PDF → Drive → Sheet | Kiểm trùng (DB + Sheet) → Drive (tìm theo md5, không upload 2 lần) → so md5 → ghi A, D–J (B, C trống) → K = "Xem phôi". **Mất phản hồi khi ghi Sheet → không ghi trùng dòng.** Lỗi mạng Google → tự thử lại | Dòng bắt đầu dữ liệu là một ô trong Cài đặt (mặc định 3). Sheet anh đưa (bản sao “NL 2026 (New)”, tab Phoi US) không có dòng tên cột, nên đã đặt **2**. Nút "Kiểm tra Google" hiện dòng 1–2 để đối chiếu |
| California (bản scan) | AI đọc + đối chiếu số hồ sơ / tên với trang 2 | Gọi AI thật |
| Sheet → miền iNET → B | Kiểm tra qua API (chỉ đọc) → xác nhận → bản ghi A (1 mục ACTION_ADD, không sửa/xoá bản ghi cũ) → miền phụ trên cPanel → chờ DNS (tối đa 12 giờ, hỏi 2 resolver) → **ghi B chỉ khi ô A vẫn đúng công ty và B vẫn trống**. Chạy lại không tạo trùng bản ghi / miền phụ | IP hosting mà cPanel báo (`DomainInfo.ip`) có thể là IP nội bộ nếu server sau NAT: lần kiểm tra đầu sẽ cho thấy |
| B → web → cPanel → SSL → C | Mẫu + nội dung AI (kiểm không bịa) → 7 ảnh Pexels/Pixabay tải kèm → **không ghi đè file có sẵn trong thư mục** (chạy lại chỉ thay file của chính web) → AutoSSL (chờ tối đa 24 giờ, gửi lại mỗi 2 giờ) → kiểm HTTPS → **ghi C chỉ khi C vẫn trống** | Một số host tắt quyền `start_autossl_check` của user: nếu vậy lần chạy thử sẽ báo rõ |
| Toàn tuyến | 1 test PDF → B → C trên cùng một Sheet giả; **128 test** tự động; E2E giao diện: đăng nhập 21/21, ghi DNS 16/16, Cài đặt ảnh 8/8, xem trước 15 mẫu 15/15 | — |

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
