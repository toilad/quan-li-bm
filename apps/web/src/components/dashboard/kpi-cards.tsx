import { FileText, Globe2, MonitorCheck, TriangleAlert, ArrowUpRight, type LucideIcon } from "lucide-react";
import { SparkBars } from "@/components/ui/charts";
import { COMPANIES, TRENDS } from "@/lib/mock-data";

type Kpi = {
  label: string;
  value: number;
  delta: string;
  deltaTone: "up" | "bad";
  hint: string;
  icon: LucideIcon;
  tint: string; // card gradient
  iconBg: string;
  bar: string;
  trend: number[];
};

export function KpiCards() {
  const count = (fn: (c: (typeof COMPANIES)[number]) => boolean) => COMPANIES.filter(fn).length;

  const kpis: Kpi[] = [
    {
      label: "PDF đã xử lý",
      value: count((c) => c.stages.pdf === "done"),
      delta: "+5 hôm nay",
      deltaTone: "up",
      hint: "Đã ghi Sheet + lưu PDF gốc lên Drive",
      icon: FileText,
      tint: "from-[#1b2a6b]/70 to-[#121a45]/40",
      iconBg: "bg-indigo-500/20 text-indigo-200",
      bar: "#7c8cff",
      trend: TRENDS.pdf,
    },
    {
      label: "Miền đã tạo",
      value: count((c) => c.stages.domain === "done"),
      delta: "+3 hôm nay",
      deltaTone: "up",
      hint: "Đã ghi cột B sau khi kiểm tra thành công",
      icon: Globe2,
      tint: "from-[#0f4a4a]/60 to-[#0b2530]/40",
      iconBg: "bg-emerald-500/20 text-emerald-200",
      bar: "#34d399",
      trend: TRENDS.domain,
    },
    {
      label: "Web đã xuất bản",
      value: count((c) => c.stages.web === "done"),
      delta: "+2 hôm nay",
      deltaTone: "up",
      hint: "HTTPS hoạt động, đã ghi cột C",
      icon: MonitorCheck,
      tint: "from-[#33207a]/65 to-[#1a1446]/40",
      iconBg: "bg-violet-500/20 text-violet-200",
      bar: "#a78bfa",
      trend: TRENDS.web,
    },
    {
      label: "Lỗi cần kiểm tra",
      value: count((c) => Object.values(c.stages).some((s) => s === "error" || s === "conflict")),
      delta: "+2 hôm nay",
      deltaTone: "bad",
      hint: "Gồm lỗi API, thiếu dữ liệu PDF, xung đột ghi Sheet",
      icon: TriangleAlert,
      tint: "from-[#5a1730]/65 to-[#2a0f22]/40",
      iconBg: "bg-rose-500/20 text-rose-200",
      bar: "#fb7185",
      trend: TRENDS.error,
    },
  ];

  return (
    <section className="grid grid-cols-1 gap-5 sm:grid-cols-2 2xl:grid-cols-4">
      {kpis.map((k) => (
        <article key={k.label} title={k.hint} className={`panel relative overflow-hidden bg-gradient-to-br ${k.tint} p-5`}>
          <div className="flex items-start gap-4">
            <span className={`grid size-12 shrink-0 place-items-center rounded-2xl ${k.iconBg}`}>
              <k.icon className="size-6" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-[14px] text-fg-muted">{k.label}</div>
              <div className="mt-1 text-[32px] font-bold leading-none tracking-tight">{k.value}</div>
              <div
                className={`mt-2 inline-flex items-center gap-1 text-[12px] font-medium ${
                  k.deltaTone === "up" ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                <ArrowUpRight className="size-3.5" />
                {k.delta}
              </div>
            </div>
            <div className="self-end">
              <SparkBars values={k.trend} color={k.bar} />
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}
