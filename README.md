# Quản Lí BM

Web App quản trị online: đọc PDF doanh nghiệp → Google Sheets/Drive, tạo miền iNET, dựng website + SSL.

> Tên app: **Quản Lí BM** (trước đây gọi là WebsiteGenerator Studio). Thư mục dự án vẫn là `WebsiteGenerator-Studio`.

Ba chức năng **độc lập**, mỗi chức năng chỉ ghi cột của mình trên Google Sheet:

| Chức năng | Điều kiện dòng | Ghi cột |
|---|---|---|
| PDF Manager | dòng mới từ PDF | A, D–J, K ("Xem phôi") — **B, C để trống** |
| Domain Manager | B trống | B — chỉ khi tạo miền thành công |
| SSL + Website Builder | B có, C trống | C — chỉ khi HTTPS hoạt động |

## Trạng thái

Backend thật đã có; dịch vụ ngoài chạy khi được cấu hình. Chi tiết: [docs/STATUS.md](docs/STATUS.md).

## Cấu trúc

```
apps/web/            Next.js + React + TypeScript + Tailwind (giao diện)
apps/api/app/        FastAPI (REST)
apps/api/worker/     Worker xử lý hàng đợi
apps/api/wg_core/    integrations/ (Google, iNET, cPanel, AI, DNS) · modules/ (pdf, domains, websites) · jobs, models, db
apps/api/tests/      Kiểm thử (mọi API ngoài đều mock)
docker-compose.yml   db + api + worker + web + backup
docs/                Kiến trúc, trạng thái, tài liệu API, phân tích app cũ
```

## Chạy trên máy (không cần Docker)

```bash
cd apps/api
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
cp .env.example .env            # điền khoá; để trống → app báo "Chưa cấu hình"
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --no-access-log   # PostgreSQL nhúng tự chạy trong .pgdata
.venv/Scripts/python -m worker.main                        # cửa sổ khác
.venv/Scripts/python -m pytest                             # kiểm thử
.venv/Scripts/python -m scripts.backup create              # sao lưu
```

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000 — gọi API ở NEXT_PUBLIC_API_URL (mặc định http://localhost:8000)
```

## Chạy bằng Docker

```bash
cp apps/api/.env.example apps/api/.env      # điền khoá
echo POSTGRES_PASSWORD=... > .env           # mật khẩu database
mkdir secrets                               # đặt google-service-account.json vào đây
docker compose up -d --build                # web :3000, api :8000
```

## Tài liệu

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — kiến trúc đã duyệt, sao lưu & khôi phục
- [docs/LEGACY-ANALYSIS.md](docs/LEGACY-ANALYSIS.md) — những gì xác minh được từ WebsiteGenerator.exe cũ

## Đồng bộ GitHub Private (chưa làm — cần chủ dự án tạo repo)

1. Tạo repo **Private** trống trên github.com (không thêm README/.gitignore).
2. `git remote add origin https://github.com/<tài-khoản>/quan-li-bm.git`
3. `git push -u origin main develop`
4. Bật bảo vệ nhánh `main` (Settings → Branches). `.env`, PDF thật, database, bản sao lưu đều đã bị `.gitignore` chặn.
