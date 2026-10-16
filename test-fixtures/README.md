# test-fixtures

Phôi PDF thật dùng để kiểm thử backend đọc PDF. **Không commit** — thư mục này bị `.gitignore` chặn, chỉ file README này
được đưa vào Git. Không ghi tên file, tên công ty hay mã số thật vào bất kỳ file nào trong Git.

- Đặt file vào `test-fixtures/pdf/` (đã được chủ dự án đồng ý dùng để kiểm thử, ngày 2026-10-16): hiện có 3 Comprovante
  CNPJ (Brazil, có lớp chữ) và 1 California LLC-1 (bản scan). Kiểm thử tự phân loại theo nội dung, không theo tên file.
- Giá trị mong đợi (đã đối chiếu bằng mắt với phôi): `test-fixtures/expected.local.json`, khoá theo md5 của file — cũng không commit.
- Kiểm thử chỉ **đọc**, không sửa file.
