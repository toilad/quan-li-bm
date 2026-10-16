# Kiến trúc WebsiteGenerator Studio

Đã được chủ dự án duyệt hướng: Next.js + React, FastAPI, PostgreSQL, Docker, GitHub Private.

## Thành phần

```
Trình duyệt ──HTTPS──► Caddy ─┬─► web     Next.js (giao diện)
                              └─► api     FastAPI (đăng nhập, phân quyền, REST, tiến độ realtime)
                                  worker  Python, nhận việc từ hàng đợi
                                  postgres dữ liệu + hàng đợi + nhật ký
                                  backup  restic → kho lưu trữ độc lập (B2/R2)
```

- `api` và `worker` dùng chung gói Python `wg_core`:
  - `integrations/` — sheets, drive, inet, cpanel, ftp, ai (mỗi dịch vụ ngoài một adapter)
  - `modules/` — `pdf_ingest`, `domains`, `websites` (không module nào gọi module khác)
  - `templates/` — 15 mẫu cũ + quy tắc nhận diện ngành
- Hàng đợi: PostgreSQL (procrastinate). Việc đã xếp hàng tồn tại qua khởi động lại; đóng trình duyệt không ảnh hưởng.

## Quy tắc ghi Google Sheets (chống xung đột)

1. Mỗi module chỉ được ghi cột của mình (PDF: A, D–K; Miền: B; Web: C).
2. Ngay trước khi ghi: đọc lại ô trực tiếp từ Sheet. Ô đã có giá trị → **xung đột**, bỏ qua, ghi nhật ký, không ghi đè.
3. Ghi theo ô cụ thể (`values.update` một ô), không ghi cả dòng/khối.
4. Dòng mới của PDF Manager được append; trước đó kiểm tra trùng theo `J + H` (mã số + bang) và md5 file.
5. Mỗi lần ghi lưu vào bảng `sheet_writes` (ô, giá trị cũ, giá trị mới, job, thời điểm) để truy vết và hoàn tác.

Khoá chống trùng (idempotency): `pdf:{md5}:{state}:{controlId}`, `domain:{domain}`, `web:{domain}` —
xem `apps/web/src/lib/sheet-rules.ts`.

## Bí mật

- Chỉ nằm phía server. Key tích hợp (OpenAI/Claude, iNET, cPanel, FTP, Google) mã hoá trong DB bằng master key.
- Master key + mật khẩu hạ tầng lưu trong trình quản lý mật khẩu của chủ dự án. **Mất master key = không giải mã được key trong backup.**
- Log tự che key/mật khẩu. Giao diện chỉ hiện dạng `sk-p…***`.

## Sao lưu & khôi phục

| Lớp | Cách làm |
|---|---|
| Mã nguồn | GitHub Private; `develop` → `main` qua PR; `main` được bảo vệ; tag mỗi bản phát hành |
| Database | `pg_dump` hằng ngày, mã hoá restic → B2/R2 (khác nhà cung cấp VPS); giữ 7 ngày / 4 tuần / 12 tháng |
| File | Mẫu web, site đã build, PDF chờ upload: cùng restic |
| Google Sheet | Mỗi đêm xuất bản sao (kèm lịch sử `sheet_writes` trong DB) — không chỉ CSV |
| Trước mỗi cập nhật | Backup DB tự động; migration chỉ thêm, không xoá cột/dữ liệu; xoá mềm |
| Snapshot VPS | Hằng tuần (lớp phụ) |
| Kiểm tra khôi phục | Hằng tháng tự khôi phục vào DB tạm, chạy kiểm tra, báo lên Dashboard |

Khôi phục khi mất máy chủ: VPS mới → clone repo → lấy `.env` từ trình quản lý mật khẩu → `restic restore` → `docker compose up`.

## Lộ trình

1. Giao diện Dark Premium (dữ liệu giả) — **đang làm**
2. GitHub Private + khung dự án
3. Đăng nhập, database, backup, cấu hình API
4. PDF Manager
5. Website Builder + SSL
6. Domain Manager (iNET)
7. Staging → production (chỉ khi được duyệt)
