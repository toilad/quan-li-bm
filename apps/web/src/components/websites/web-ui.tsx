import clsx from "clsx";
import { Check, Loader2, X, AlertTriangle, Clock3, Minus, type LucideIcon } from "lucide-react";
import { WEB_STEPS, type WebRow, type WebStatus } from "@/lib/web-mock";

export const WEB_STATUS: Record<WebStatus, { label: string; icon: LucideIcon; cls: string; spin?: boolean }> = {
  idle: { label: "Chưa chạy", icon: Minus, cls: "border-white/[0.08] bg-white/[0.03] text-fg-subtle" },
  queued: { label: "Trong hàng đợi", icon: Clock3, cls: "border-indigo-400/25 bg-indigo-400/10 text-indigo-200" },
  running: { label: "Đang dựng", icon: Loader2, cls: "border-sky-400/30 bg-sky-400/10 text-sky-300", spin: true },
  done: { label: "HTTPS · đã ghi C", icon: Check, cls: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" },
  failed: { label: "Thất bại", icon: X, cls: "border-rose-400/35 bg-rose-500/10 text-rose-300" },
  conflict: { label: "Xung đột ô C", icon: AlertTriangle, cls: "border-amber-400/35 bg-amber-400/10 text-amber-300" },
};

export function WebStatusChip({ status }: { status: WebStatus }) {
  const s = WEB_STATUS[status];
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-semibold", s.cls)}>
      <s.icon className={clsx("size-3", s.spin && "animate-spin")} /> {s.label}
    </span>
  );
}

export type StepState = "done" | "run" | "fail" | "todo" | "warn";

export function webStepState(r: WebRow, i: number): StepState {
  if (r.status === "done") return "done";
  if (r.status === "conflict") return i < WEB_STEPS.length - 1 ? "done" : "warn";
  if (r.status === "idle" || r.status === "queued") return i < r.step ? "done" : "todo";
  if (i < r.step) return "done";
  if (i > r.step) return "todo";
  return r.status === "failed" ? "fail" : "run";
}

export function WebStepBar({ r }: { r: WebRow }) {
  return (
    <div className="flex gap-0.5">
      {WEB_STEPS.map((s, i) => {
        const st = webStepState(r, i);
        return (
          <span
            key={s}
            title={s}
            className={clsx(
              "relative h-1.5 w-5 overflow-hidden rounded-full",
              st === "done" ? "bg-emerald-400" : st === "fail" ? "bg-rose-400" : st === "warn" ? "bg-amber-400" : "bg-white/[0.08]",
            )}
          >
            {st === "run" && <span className="absolute inset-y-0 left-0 rounded-full bg-sky-400 transition-[width] duration-500" style={{ width: `${Math.max(15, r.progress)}%` }} />}
          </span>
        );
      })}
    </div>
  );
}
