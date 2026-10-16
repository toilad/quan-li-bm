# Phân tích WebsiteGenerator.exe (app cũ)

Phân tích tĩnh ngày 2026-10-16 — exe **không được chạy**, không bị sửa.
File gốc: `Downloads\WebsiteGenerator.exe`, SHA256 `bc1cc2c75a92b97ff86585db617c003f3ecac11472b59880921ee08bc214d4ee`.

- Python 3.12, PyInstaller onefile, giao diện tkinter, không ký số.
- Source gốc từng nằm ở máy khác: `C:\Users\Vantinh\Downloads\Telegram Desktop\website-generator\...`.
  Không tìm thấy backup nào trên máy hiện tại.
- ⚠️ Exe nhúng `.app_settings.json` chứa OpenAI key và mật khẩu 2 tài khoản FTP dạng rõ → cần đổi nếu exe từng được chia sẻ.
  Dự án mới **không dùng lại** các giá trị này.

## Module tìm thấy

`app` (GUI) và `src.{ai_generator, config, excel_loader, ftp_uploader, gdrive_loader, paths, site_builder, templates.{base, home, about, contact, faq, privacy, terms}}`.

## Đã xác minh

| Hạng mục | Chi tiết |
|---|---|
| OCR phôi | OpenAI `gpt-4o-mini` vision; PDF → render trang 1 thành PNG để đọc. Prompt loại địa chỉ/email Registered Agent; `control_id` giữ nguyên dấu gạch |
| Ghi Sheet cũ | Webhook Apps Script `doPost`, chỉ **append**; dòng 1 tiêu đề, dòng 2 header, dữ liệu từ dòng 3; tab "Phoi US" / "Tinh Tool" |
| Cột cũ | A business_name, B site_host, C site_url, D phone, E ten_thuong (slug giữ LLC), F address, G city, H state, I zip, J control_id. Không có K, L. Bản cũ **có ghi B, C khi OCR** — yêu cầu mới thì không |
| Google Drive | `gdrive_loader` chỉ **tải** Excel/CSV từ link công khai. Không có upload PDF |
| Tạo miền | GUI mô tả: quét dòng có E mà B trống → tạo bản ghi A trên iNET Portal (IP theo nick) + "Create A New Domain" trên cPanel → ghi B. Random đuôi trong 5 nick, mở trình duyệt từng nick, 30 dòng/lượt. Ví dụ miền: `globalfreight.th-ntp.com` |
| SSL + web | "Bật SSL + Tạo web (30 dòng/lượt)", cPanel AutoSSL, chờ ~40 phút sau DNS |
| **Thiếu** | `src.domain_creator` **không có trong exe**; không có thư viện điều khiển trình duyệt → Tạo miền / bật SSL không chạy được ở bản này |
| Site builder | 7 trang; nội dung từ Claude (`claude-opus-4-5`) hoặc OpenAI (`gpt-4o-mini`), JSON schema cố định; cấm bịa giải thưởng/khách hàng/số liệu |
| Mẫu | 15 mẫu có tên (xem `apps/web/src/lib/templates.ts`), 14 bảng màu, 15 font, 6 kiểu hero |
| FTP | Upload lên `/public_html/<domain>/`, profile FTP nhiều tài khoản, tuỳ chọn TLS |
| FB | Chèn meta tag xác minh domain, FB App ID cho nút đăng nhập trên trang Contact |
| Không có | WA SOS PDF, Brazil CNPJ (thuộc bản mới đã mất) |

## Khôi phục logic

Bytecode Python 3.12 — chưa có trình dịch ngược hoàn hảo. Kế hoạch: dùng `dis` + đọc chuỗi để viết lại,
kiểm thử đối chiếu đầu ra (HTML) với bản cũ. Prompt, HTML/CSS, text giao diện lấy lại nguyên văn.
