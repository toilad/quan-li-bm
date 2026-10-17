import { ScreenPlaceholder } from "@/components/shell/screen-placeholder";

export default function Page() {
  return (
    <ScreenPlaceholder
      title="Kho mẫu web"
      subtitle="15 mẫu (tên từ app cũ, giao diện mới), quản lý theo nhóm ngành"
      planned={["Lưới thumbnail 15 mẫu, lọc theo nhóm ngành", "Xem trước toàn trang với dữ liệu doanh nghiệp mẫu", "Bảng quy tắc nhận diện ngành → mẫu, chỉnh được", "Thống kê số website đã dùng từng mẫu"]}
    />
  );
}
