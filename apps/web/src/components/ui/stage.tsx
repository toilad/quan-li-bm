import clsx from "clsx";
import { Check, Loader2, Clock3, X, AlertTriangle, Minus } from "lucide-react";
import type { StageStatus } from "@/lib/mock-data";
import type { ModuleKey } from "@/lib/sheet-rules";

export const STAGE_LABEL: Record<ModuleKey, string> = { pdf: "PDF", domain: "Miền", web: "Web" };

const STYLE: Record<StageStatus, { cls: string; icon: typeof Check; text: string }> = {
  done: { cls: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300", icon: Check, text: "Xong" },
  running: { cls: "border-sky-400/30 bg-sky-400/10 text-sky-300", icon: Loader2, text: "Đang chạy" },
  queued: { cls: "border-indigo-400/25 bg-indigo-400/10 text-indigo-200", icon: Clock3, text: "Trong hàng đợi" },
  error: { cls: "border-rose-400/35 bg-rose-500/10 text-rose-300", icon: X, text: "Lỗi" },
  conflict: { cls: "border-amber-400/35 bg-amber-400/10 text-amber-300", icon: AlertTriangle, text: "Xung đột" },
  idle: { cls: "border-white/[0.06] bg-white/[0.02] text-fg-subtle", icon: Minus, text: "Chưa chạy" },
};

/** One compact chip per module: PDF / Miền / Web. */
export function StageChip({ module, status }: { module: ModuleKey; status: StageStatus }) {
  const s = STYLE[status];
  const Icon = s.icon;
  return (
    <span
      title={`${STAGE_LABEL[module]}: ${s.text}`}
      className={clsx("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-semibold", s.cls)}
    >
      <Icon className={clsx("size-3", status === "running" && "animate-spin")} />
      {STAGE_LABEL[module]}
    </span>
  );
}

export function StageLegend() {
  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-fg-subtle">
      {(Object.keys(STYLE) as StageStatus[]).map((k) => {
        const Icon = STYLE[k].icon;
        return (
          <span key={k} className="inline-flex items-center gap-1">
            <Icon className={clsx("size-3", STYLE[k].cls.split(" ").find((c) => c.startsWith("text-")))} />
            {STYLE[k].text}
          </span>
        );
      })}
    </div>
  );
}
