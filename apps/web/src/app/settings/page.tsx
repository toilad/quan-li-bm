import { Topbar } from "@/components/shell/topbar";
import { ApiSettings } from "@/components/settings/api-settings";

export default function SettingsPage() {
  return (
    <>
      <Topbar title="Cài đặt API" subtitle="Kết nối Google, AI, iNET và cPanel — bí mật chỉ lưu phía server, đã mã hoá, không hiển thị lại." />
      <ApiSettings />
    </>
  );
}
