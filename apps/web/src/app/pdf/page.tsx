import { ScreenPlaceholder } from "@/components/shell/screen-placeholder";

export default function Page() {
  return (
    <ScreenPlaceholder
      title="PDF Manager"
      subtitle="Tải PDF gốc lên, trích xuất thông tin, ghi Google Sheets và lưu PDF lên Drive"
      planned={["Kéo thả một hoặc nhiều PDF, xem danh sách và trạng thái từng file", "Bảng đối chiếu dữ liệu trích xuất trước khi ghi — trường thiếu được đánh dấu, không tự bịa", "Cảnh báo trùng (cùng mã số doanh nghiệp hoặc cùng file) trước khi tạo dòng mới", "Ghi A, D–J và link Xem phôi cột K — B, C luôn để trống", "Kiểm tra link Drive mở đúng file gốc, đối chiếu md5"]}
    />
  );
}
