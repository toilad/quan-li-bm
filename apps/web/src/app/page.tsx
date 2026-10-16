import { Topbar } from "@/components/shell/topbar";
import { KpiCards } from "@/components/dashboard/kpi-cards";
import { CompanyTable } from "@/components/dashboard/company-table";
import { ModuleProgress } from "@/components/dashboard/module-progress";
import { TemplateShowcase } from "@/components/dashboard/template-showcase";
import { ActivityFeed } from "@/components/dashboard/activity-feed";

export default function DashboardPage() {
  return (
    <>
      <Topbar title="Tổng quan" subtitle="Theo dõi dữ liệu doanh nghiệp, tên miền và website — 3 chức năng chạy độc lập" />
      <div className="space-y-5">
        <KpiCards />
        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_400px]">
          <CompanyTable />
          <ModuleProgress />
        </div>
        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_400px]">
          <TemplateShowcase />
          <ActivityFeed />
        </div>
      </div>
    </>
  );
}
