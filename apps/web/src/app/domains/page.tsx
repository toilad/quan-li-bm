import { Topbar } from "@/components/shell/topbar";
import { DomainManager } from "@/components/domains/domain-manager";

export default function DomainsPage() {
  return (
    <>
      <Topbar
        title="Tạo miền iNET"
        subtitle="Dòng có cột B trống → tạo miền phụ trên miền gốc của nick (DNS + cPanel) → xác minh → ghi cột B. Cột C giữ nguyên."
      />
      <DomainManager />
    </>
  );
}
