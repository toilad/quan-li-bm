import { Topbar } from "@/components/shell/topbar";
import { WebBuilder } from "@/components/websites/web-builder";

export default function WebsitesPage() {
  return (
    <>
      <Topbar
        title="SSL + Tạo web"
        subtitle="Dòng có miền ở B và C trống → nhận diện ngành, chọn mẫu → AI viết nội dung → dựng & upload qua cPanel API → AutoSSL → kiểm tra HTTPS → ghi C."
      />
      <WebBuilder />
    </>
  );
}
