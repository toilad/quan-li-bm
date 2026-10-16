import { ScreenPlaceholder } from "@/components/shell/screen-placeholder";

export default function Page() {
  return (
    <ScreenPlaceholder
      title="Nhật ký hoạt động"
      subtitle="Toàn bộ tác vụ chạy trên server: hoàn thành, đang chạy, thất bại"
      planned={["Lọc theo module, trạng thái, thời gian, người chạy", "Chi tiết từng tác vụ: từng bước, thời gian, lỗi, lần thử lại", "Lịch sử ghi Google Sheets — ô nào, giá trị cũ / mới, xung đột", "Lịch sử sao lưu và kiểm tra khôi phục"]}
    />
  );
}
