# WebsiteGenerator Studio

Web App quản trị online: đọc PDF doanh nghiệp → Google Sheets/Drive, tạo miền iNET, dựng website + SSL.
Ba chức năng **độc lập**, mỗi chức năng chỉ ghi cột của mình trên Google Sheet:

| Chức năng | Điều kiện dòng | Ghi cột |
|---|---|---|
| PDF Manager | dòng mới từ PDF | A, D–J, K ("Xem phôi") — **B, C để trống** |
| Domain Manager | B trống | B — chỉ khi tạo miền thành công |
| SSL + Website Builder | B có, C trống | C — chỉ khi HTTPS hoạt động |

## Trạng thái

**Giai đoạn 1 — thiết kế giao diện (dữ liệu giả).** Chưa kết nối API thật.

## Cấu trúc

```
apps/web/        Next.js + React + TypeScript + Tailwind (giao diện)
apps/api/        FastAPI (giai đoạn 2+)
apps/worker/     Worker xử lý hàng đợi (giai đoạn 2+)
docs/            Kiến trúc, phân tích app cũ, quy tắc dữ liệu
```

## Chạy giao diện

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

## Tài liệu

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — kiến trúc đã duyệt, sao lưu & khôi phục
- [docs/LEGACY-ANALYSIS.md](docs/LEGACY-ANALYSIS.md) — những gì xác minh được từ WebsiteGenerator.exe cũ
