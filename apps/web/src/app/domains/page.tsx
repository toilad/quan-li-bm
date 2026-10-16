import { ScreenPlaceholder } from "@/components/shell/screen-placeholder";

export default function Page() {
  return (
    <ScreenPlaceholder
      title="Tạo miền iNET"
      subtitle="Quét dòng có cột B trống, tạo miền qua iNET và cPanel, chỉ ghi B khi thành công"
      planned={["Số dòng đủ điều kiện (B trống) và chọn số lượng xử lý mỗi lượt", "Xem trước tên miền sẽ tạo theo quy tắc, phát hiện trùng trước khi chạy", "Tiến trình từng miền: tạo bản ghi → cấu hình cPanel → kiểm tra DNS", "Danh sách thất bại kèm lý do và nút thử lại", "Phân bổ theo tài khoản iNET, giới hạn tốc độ từng tài khoản"]}
    />
  );
}
