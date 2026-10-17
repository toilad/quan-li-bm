# API iNET và cPanel — tra cứu tài liệu chính thức

Tra cứu ngày 2026-10-16, **chỉ từ tài liệu chính thức**. Mọi endpoint dưới đây có trong tài liệu và kèm nguồn.
Mục ghi "chưa có trong tài liệu" thì **không được tự đoán** khi lập trình. Nguyên tắc: 100% qua API, không dùng điều khiển trình duyệt.
Thiếu API hoặc thiếu quyền → báo "Bị chặn".

Các mục đánh dấu ✔ đã được kiểm tra trực tiếp lại trên trang nguồn.

## iNET — developers.inet.vn

- Có API công khai, 1 khoá dùng cho Domain, DNS, SSL, Hosting… Đăng ký qua iNET SSO.
  Base URL `https://developers.inet.vn/api/gateway/v1`. Header `Authorization: Bearer inet_sk_...`.
  Khoá có phạm vi `read` hoặc `write` và chỉ hiển thị 1 lần.
  Nguồn: https://developers.inet.vn/docs/getting-started/authentication
- ✔ Giới hạn: 60 yêu cầu/phút · 1.000/giờ · 10.000/ngày. Mọi khoá dùng chung mức này.
  Vượt giới hạn → HTTP 429 + header `Retry-After`. Có header `X-RateLimit-*`.
  Nguồn: https://developers.inet.vn/docs/getting-started/rate-limits
- ✔ DNS (nguồn: https://developers.inet.vn/api-reference):
  - `GET /domain/{domainId}/record`: liệt kê bản ghi, áp dụng cho miền dùng ns1/ns2.inet.vn.
  - `PATCH /domain/{domainId}/record`: cập nhật bản ghi DNS.
  - `PATCH /domain/{domainId}/nameserver`.
  - Không có endpoint tạo hoặc xoá riêng.
  - ✔ **Cập nhật 2026-10-17: tài liệu đã mô tả đủ** (dữ liệu có cấu trúc trên trang api-reference, mở từng endpoint là thấy):
    - `PATCH /domain/{domainId}/record` body `{recordList: [{domainId, name, type, data, ttl, action, id?}]}`.
      Bắt buộc: `domainId, name, type, data, action`. `action` = `ACTION_ADD` (thêm, không cần id) hoặc `ACTION_DELETE` (xoá, cần id).
      Sửa = 1 mục DELETE + 1 mục ADD. `ttl` kiểu chuỗi, tính bằng giây (vd "300"). Trả về `recordList` sau khi cập nhật.
      Tức là gửi từng thao tác, không phải thay toàn bộ danh sách bản ghi.
    - `GET /domain/{domainId}/record` → `{id, name, recordList: [{id, name, type, data, ttl, priority, createdDate}]}`.
    - `GET /domain?name=&status=&page=&pageSize=` → `{content: [{id, name, status, …}], totalPages, totalElements, size, number}`.
    - `GET /domain/{domainId}` → `{…, nsList: [{id, hostname}]}`, dùng để kiểm tra miền có dùng ns1/ns2.inet.vn không.
  - Không có file OpenAPI/Postman công khai. `/api/gateway/v1/*` trả 401 khi chưa có khoá.
  - **Ý nghĩa của PATCH /record (đối chiếu):** tài liệu ghi "Thêm hoặc xóa DNS records" và "Mỗi item là 1 thao tác thêm hoặc xóa".
    Sửa được mô tả là 1 DELETE + 1 ADD. Tức là mỗi mục là một thao tác, không phải gửi lại cả danh sách bản ghi.
    Gửi 1 mục ACTION_ADD nghĩa là thêm đúng 1 bản ghi.
    App vẫn kiểm tra thêm khi chạy: danh sách iNET trả về sau PATCH phải còn đủ mọi bản ghi có trước đó (so theo id).
    Thiếu bản ghi nào thì dừng ngay, báo lỗi, không làm bước tiếp.
- ✔ Hosting: `GET/POST /hosting/{hostingId}/addon`, `DELETE /hosting/{hostingId}/addon/{id}`, `POST /hosting/{hostingId}/addon/sync`.
  Tài liệu **không có** endpoint subdomain, SSL hay upload file cho hosting.
- iNET còn có OnePanel (panel riêng). Cần xác nhận hosting thực tế là cPanel hay OnePanel.

## cPanel UAPI — api.docs.cpanel.net

- Gọi qua `https://HOST:2083/execute/<Module>/<function>?…` với header `Authorization: cpanel USER:TOKEN`.
  Token tạo ở Security › Manage API Tokens, mặc định hết hạn sau 1 năm. Nhà cung cấp hosting có thể ẩn tính năng này.
  Nguồn: https://api.docs.cpanel.net/cpanel/tokens/ · https://docs.cpanel.net/cpanel/security/manage-api-tokens-in-cpanel/
- ✔ `SubDomain::addsubdomain`: bắt buộc `domain`, `rootdomain` (phải có sẵn trên tài khoản); `dir` tuỳ chọn.
  Cần bật vai trò Web Server. Có thêm `listsubdomains`, `delsubdomain`.
  Nguồn: https://api.docs.cpanel.net/specifications/cpanel.openapi/subdomain/subdomain-addsubdomain.md
- `DNS::mass_edit_zone`: cần `zone`, `serial` (phải khớp SOA hiện tại; lấy qua `DNS::parse_zone`), `add`/`edit`/`remove`.
  Dùng `DNS::has_local_authority` để kiểm tra server có phải nơi quản lý DNS không.
  Nguồn: https://api.docs.cpanel.net/specifications/cpanel.openapi/dns/dns-mass_edit_zone.md
- SSL: `SSL::start_autossl_check`, `SSL::is_autossl_check_in_progress`, `SSL::get_autossl_problems`, `SSL::installed_hosts`.
  AutoSSL do nhà cung cấp bật ở cấp WHM. Nguồn: https://docs.cpanel.net/whm/ssl-tls/manage-autossl/
- Upload file: `Fileman::upload_files` (cần vai trò File Storage), hoặc FTP/FTPS.
- ✔ Document root (đọc trước khi upload, không đoán đường dẫn):
  - Miền phụ: `SubDomain::listsubdomains` (lọc bằng `regex`) → `dir` (đường dẫn tuyệt đối), `basedir` (tương đối thư mục home), `reldir`.
    Nguồn: https://api.docs.cpanel.net/specifications/cpanel.openapi/subdomain/subdomain-listsubdomains.md
  - Miền chính / addon: `DomainInfo::single_domain_data` (`domain` bắt buộc, không dùng alias) → `result.data.documentroot`, `result.data.type`.
    Nguồn: https://api.docs.cpanel.net/specifications/cpanel.openapi/domain-information/domaininfo-single_domain_data.md
  - Không tìm thấy miền trên tài khoản → dừng, không upload, C giữ trống.
- ✔ IP hosting: `DomainInfo::single_domain_data` trả về `result.data.ip` ("The domain's IP address").
  Phải khớp IP cấu hình của nick, nếu không thì không tạo bản ghi A.
- ✔ `DNS::has_local_authority` (`domain` bắt buộc) → `local_authority` 1/0, `nameservers`, `zone`, chỉ đọc.
  Dùng để biết miền có đang dùng DNS của hosting cPanel không.
  Nguồn: https://api.docs.cpanel.net/specifications/cpanel.openapi/dns/dns-has_local_authority.md
- Giới hạn tốc độ của UAPI: chưa có trong tài liệu.
- ✔ Phiên bản cPanel (chỉ đọc): `StatsBar::get_stats` với `display=cpanelversion` → mục `count` là phiên bản máy chủ.
  Nút "Kiểm tra nick" gọi hàm này. Các trang tài liệu đã tra ứng với API bản 11.138; tài liệu không ghi các hàm trên có từ bản nào.
  Vì vậy em chỉ hiện phiên bản để đối chiếu, không tự đặt ngưỡng tối thiểu.
  Nguồn: https://api.docs.cpanel.net/openapi/cpanel/operation/get_stats

## Pexels — ảnh cho website (ưu tiên khi có khoá)

Nguồn: https://www.pexels.com/api/documentation/ (tra 2026-10-17).
Tài khoản mới hiện không được cấp khoá ("New API key issuance is currently paused"), nhưng khoá đã cấp trước đó vẫn dùng được.
- ✔ Khoá gửi trong header `Authorization: <khoá>`, không đặt trong URL.
- ✔ `GET https://api.pexels.com/v1/search?query=&orientation=landscape|portrait|square&per_page=(≤80)&page=`.
- ✔ Mỗi ảnh có `src`: `portrait` (800×1200), `landscape` (1200×627), `large` (940×650)…
  Ngoài ra có `alt`, `photographer`, `photographer_url`, `url`.
- ✔ Giới hạn 200 yêu cầu/giờ, 20.000/tháng.
- ✔ Hướng dẫn: hiện link nổi bật về Pexels và ghi tên nhiếp ảnh gia. App ghi "Photos by … on Pexels".
- App tải ảnh về và upload kèm web.

## Pixabay — ảnh cho website (dùng khi không có khoá Pexels)

Nguồn: https://pixabay.com/api/docs/ (tra 2026-10-17).
Pexels đã được tích hợp trước, nhưng ngày 2026-10-17 trang khoá Pexels báo "New API key issuance is currently paused", nên app chuyển sang Pixabay.
- ✔ `GET https://pixabay.com/api/`, các tham số:
  - `key`, `q` (≤ 100 ký tự), `image_type=photo`;
  - `orientation=all|horizontal|vertical`, `safesearch`, `order`;
  - `page`, `per_page` (3–200).
- ✔ Mỗi kết quả có:
  - `id`, `pageURL`, `tags`;
  - `webformatURL` (≤ 640 px, link sống 24 giờ), `largeImageURL` (≤ 1280 px);
  - `imageWidth`, `imageHeight`, `user_id`, `user`.
- ✔ Giới hạn 100 yêu cầu / 60 giây cho mỗi khoá.
  Vượt giới hạn → 429 "API rate limit exceeded". Header `X-RateLimit-Reset` là số giây phải chờ.
  Kết quả tìm phải lưu đệm 24 giờ.
- ✔ Quy định khi dùng ảnh:
  - **không hot-link lâu dài**, phải tải ảnh về server;
  - không tải hàng loạt có hệ thống;
  - hiện cho người xem biết ảnh lấy từ đâu.
  App làm đúng như vậy: mỗi web tải 7 ảnh và upload kèm web, chân trang ghi "Photos by … on Pixabay".
  Xem trước trong app chỉ hiển thị tạm, được phép, và kết quả được lưu đệm.
- Tài liệu không ghi mã lỗi khi khoá sai. App coi 400/401/403 khi tìm ảnh là "khoá không hợp lệ".
  Khoá nằm trong URL, nên app không bao giờ ghi URL vào nhật ký.

## Ảnh hưởng tới thiết kế

| Bước | Khả năng |
|---|---|
| Bản ghi A | Nameserver ở host cPanel → `DNS::mass_edit_zone` ✔. Nameserver iNET → `PATCH /domain/{id}/record` (ACTION_ADD), **đã tích hợp**, sau công tắc mặc định TẮT + chạy thử 1 miền + xem trước/xác nhận. NS hosting cPanel (`DNS::has_local_authority`) / Cloudflare / khác → nhận diện và không gọi API iNET; `DNS::mass_edit_zone` chưa triển khai |
| Miền phụ trên hosting | `SubDomain::addsubdomain` ✔ (cần token và vai trò Web Server) |
| SSL | Gọi được bằng API. Cấp chứng chỉ được hay không tuỳ AutoSSL bật ở WHM và DNS đã trỏ đúng |
| Upload | `Fileman::upload_files` hoặc FTPS |
| Kiểm tra HTTPS | `SSL::installed_hosts` + gọi HTTPS từ server |

Hàng đợi phải tôn trọng giới hạn iNET (60 yêu cầu/phút cho mỗi khoá) và tự chờ theo `Retry-After` khi gặp lỗi 429.

## Cần chủ dự án xác nhận

1. Nameserver của từng miền gốc: ns1/ns2.inet.vn hay của host cPanel?
2. Hosting là cPanel (cổng 2083) hay iNET OnePanel? Mục "Manage API Tokens" có hiện không?
3. AutoSSL có bật không, nhà cung cấp chứng chỉ nào? Có giới hạn số miền phụ không?
4. Có tài khoản developers.inet.vn với khoá `write` không? (Cấu trúc `PATCH /record` đã có trong tài liệu.)
5. Có chấp nhận 1 bản ghi wildcard `*.miền-gốc` trỏ về host không? Nếu được thì bỏ hẳn bước tạo A cho từng công ty. Đây là phương án thiết kế em đề xuất, không lấy từ tài liệu.
