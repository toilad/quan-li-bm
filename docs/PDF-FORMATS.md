# PDF Manager — loại phôi và quy tắc trích xuất

Đặc tả cho backend (giai đoạn 4), lập từ phôi mẫu chủ dự án cung cấp ngày 2026-10-16 (file gốc ở `test-fixtures/`, ngoài Git; mọi ví dụ dưới đây là **giá trị giả**):
1 bản scan California LLC-1 và 3 Comprovante CNPJ có lớp chữ. Kiểm tra tự động: `npm run check:pdf-rules` (apps/web).

## Nguyên tắc chung

- PDF gốc upload lên Drive **nguyên byte**, không chuyển ảnh, không sửa. Đối chiếu md5 sau upload.
- Thứ tự lưu: kiểm tra trùng (mã số + md5) → upload Drive → xác minh md5 → **lưu Drive file ID** → ghi 1 dòng A, D–K.
  Ghi Sheet lỗi: giữ Drive ID, thử lại **chỉ ghi Sheet**, không upload lại.
- B, C luôn trống. L giữ nguyên. K = link "Xem phôi".
- Mọi mã (CNPJ, Entity No., Original ID, ZIP/CEP, NÚMERO) là **văn bản**: ghi Sheet bằng `valueInputOption=RAW`
  trên cột định dạng Plain text để giữ số 0 đầu và dấu chấm/gạch.
- Không tự bịa: trường không có trên phôi → để trống + chờ người xác nhận.
  **A (tên) và J (mã đăng ký) bắt buộc**, không được để trống; nếu do AI đọc từ bản scan → bắt buộc tick "đã đối chiếu".
- "Tự lưu file hợp lệ" mặc định **tắt**; khi bật chỉ tự lưu file không có cảnh báo, không có trường do AI đọc.

## Nhận diện loại phôi

| Loại | Dấu hiệu | Lớp chữ |
|---|---|---|
| Wyoming LLC | "STATE OF WYOMING", "Articles of Organization", "Original ID" | thường có |
| California LLC | Khung "LLC-1 · Articles of Organization of a Limited Liability Company (LLC)", dấu "FILED Secretary of State State of California", số 12 chữ số góc trên phải | **scan** → AI đọc |
| Brazil CNPJ | "REPÚBLICA FEDERATIVA DO BRASIL / CADASTRO NACIONAL DA PESSOA JURÍDICA / COMPROVANTE DE INSCRIÇÃO" | có (in từ trình duyệt) |

Độ tin cậy thấp → trạng thái "Chưa nhận diện", người dùng chọn loại rồi đọc lại. Không đoán bừa.

## California LLC-1 (mẫu REV 01/2013, 2 trang)

| Cột | Lấy từ | Ghi chú |
|---|---|---|
| A | ① LLC Name (Proposed LLC Name) | vd `Example Supply Co., LLC` — giữ nguyên dấu phẩy, hậu tố |
| J | Số 12 chữ số góc trên phải trang 1 | Mẫu đã thấy có 12 chữ số. **Chưa xác nhận cấu tạo mã** (mới có 1 mẫu): chỉ kiểm tra cơ bản, khác dạng thì cảnh báo, không chặn lưu. Số lặp lại ở trang 2 (Attachment) → đối chiếu 2 trang |
| F | ③a Initial Street Address of LLC | vd `100 Example Ave.` |
| G, H, I | ③a City / State / Zip | Phôi ghi dạng `Los Angeles, California 90000` → H chuẩn hoá `CA` |
| D | — | LLC-1 **không có** ô điện thoại → trống, chờ xác nhận |
| Bỏ qua | ④ Service of Process (Agent), ⑤ Management, chữ ký organizer | Địa chỉ Agent không bao giờ dùng làm địa chỉ công ty |

## Brazil — Comprovante CNPJ (IN RFB nº 2.119/2022)

| Cột | Lấy từ ô | Ghi chú |
|---|---|---|
| A | NOME EMPRESARIAL | Giữ nguyên chữ in hoa. Có thể không có LTDA (quỹ, hiệp hội) — không cảnh báo |
| J | NÚMERO DE INSCRIÇÃO | `00.123.456/0001-49` (số giả) — giữ định dạng, kiểm tra số kiểm tra CNPJ |
| F | LOGRADOURO, NÚMERO, COMPLEMENTO - BAIRRO | Bỏ ô `********`; không lặp số nhà nếu LOGRADOURO đã chứa (vd `AV EXEMPLO 1500` + `1500`); giữ `02` |
| G | MUNICÍPIO | vd `SAO PAULO` (không dấu như in) |
| H | UF | 2 chữ, kiểm tra danh sách bang |
| I | CEP | In dạng `01.234-567` → giữ nguyên |
| D | TELEFONE | Có thể trống → chờ xác nhận |

Lưu database (không ghi Sheet): CNAE chính (ngành nghề → chọn mẫu web), CNAE phụ, natureza jurídica, nome de fantasia,
porte, data de abertura, endereço eletrônico, situação cadastral (+ ngày). Situação khác `ATIVA` → cảnh báo.

## Ngành nghề (database)

- Brazil: CNAE chính, mã giữ dạng văn bản (`01.51-2-01`).
- Wyoming / California: phôi không ghi ngành → suy từ tên công ty, người dùng sửa được.
- Lưu: `industry_raw`, `industry_code`, `industry_category`, `industry_source (doc|name|manual)` → module SSL + Tạo web dùng để chọn mẫu.

## Bảng dự kiến (giai đoạn 3–4)

- `pdf_documents`: id, md5, original_name, size, pages, doc_type, detection_confidence, drive_file_id, drive_link,
  status, failed_at, sheet_tab, sheet_row, created_by, timestamps.
- `companies`: sheet_row, A, D–J, industry_*, br_raw (jsonb), source_pdf_id.
- `sheet_writes`: ô, giá trị cũ/mới, job, thời điểm (xem ARCHITECTURE.md).
