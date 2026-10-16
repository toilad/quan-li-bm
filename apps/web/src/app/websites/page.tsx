import { ScreenPlaceholder } from "@/components/shell/screen-placeholder";

export default function Page() {
  return (
    <ScreenPlaceholder
      title="SSL + Tạo web"
      subtitle="Dòng có tên miền ở B và C trống: dựng web theo mẫu, bật SSL, kiểm tra HTTPS rồi mới ghi C"
      planned={["Danh sách dòng đủ điều kiện (B có, C trống) kèm mẫu được nhận diện", "Đổi mẫu thủ công cho từng doanh nghiệp, xem trước trước khi xuất bản", "Tiến trình từng site: nội dung AI → dựng HTML → upload → AutoSSL → kiểm tra HTTPS", "Chỉ ghi URL vào C khi HTTPS trả về thành công", "Thử lại site lỗi SSL hoặc triển khai"]}
    />
  );
}
