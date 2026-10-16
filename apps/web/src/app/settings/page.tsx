import { ScreenPlaceholder } from "@/components/shell/screen-placeholder";

export default function Page() {
  return (
    <ScreenPlaceholder
      title="Cài đặt API"
      subtitle="Kết nối Google, iNET, hosting, AI — bí mật chỉ lưu phía server, đã mã hoá"
      planned={["Google Sheets / Drive: tài khoản, Sheet, tab, thư mục lưu phôi", "Tài khoản iNET và cPanel/hosting, kiểm tra kết nối", "Khoá AI (Claude / OpenAI), chỉ hiển thị dạng che", "Người dùng và phân quyền: Admin, Vận hành, Xem", "Sao lưu: lịch chạy, số phiên bản giữ lại, kiểm tra khôi phục"]}
    />
  );
}
