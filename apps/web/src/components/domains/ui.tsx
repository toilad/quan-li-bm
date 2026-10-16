import clsx from "clsx";
import { Check, Loader2, X, AlertTriangle, Clock3, Minus, type LucideIcon } from "lucide-react";
import { DOMAIN_STEPS, type DomainRow, type RowStatus } from "@/lib/domain-mock";

export const ROW_STATUS: Record<RowStatus, { label: string; icon: LucideIcon; cls: string; spin?: boolean }> = {
  idle: { label: "Chưa chạy", icon: Minus, cls: "border-white/[0.08] bg-white/[0.03] text-fg-subtle" },
  queued: { label: "Trong hàng đợi", icon: Clock3, cls: "border-indigo-400/25 bg-indigo-400/10 text-indigo-200" },
  running: { label: "Đang tạo", icon: Loader2, cls: "border-sky-400/30 bg-sky-400/10 text-sky-300", spin: true },
  done: { label: "Thành công", icon: Check, cls: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" },
  failed: { label: "Thất bại", icon: X, cls: "border-rose-400/35 bg-rose-500/10 text-rose-300" },
  conflict: { label: "Xung đột ô B", icon: AlertTriangle, cls: "border-amber-400/35 bg-amber-400/10 text-amber-300" },
};

export function RowStatusChip({ status, label }: { status: RowStatus; label?: string }) {
  const s = ROW_STATUS[status];
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-semibold", s.cls)}>
      <s.icon className={clsx("size-3", s.spin && "animate-spin")} />
      {label ?? s.label}
    </span>
  );
}

export type StepState = "done" | "run" | "fail" | "todo" | "warn";

export function stepState(r: DomainRow, i: number): StepState {
  if (r.status === "done") return "done";
  if (r.status === "conflict") return i < DOMAIN_STEPS.length - 1 ? "done" : "warn";
  if (r.status === "idle" || r.status === "queued") {
    // after a failure + re-queue, earlier steps stay done
    return i < r.step ? "done" : "todo";
  }
  if (i < r.step) return "done";
  if (i > r.step) return "todo";
  return r.status === "failed" ? "fail" : "run";
}

/** Five compact segments, one per pipeline step. */
export function StepBar({ r }: { r: DomainRow }) {
  return (
    <div className="flex gap-1">
      {DOMAIN_STEPS.map((s, i) => {
        const st = stepState(r, i);
        return (
          <span
            key={s}
            title={s}
            className={clsx(
              "relative h-1.5 w-7 overflow-hidden rounded-full",
              st === "done" ? "bg-emerald-400" : st === "fail" ? "bg-rose-400" : st === "warn" ? "bg-amber-400" : "bg-white/[0.08]",
            )}
          >
            {st === "run" && (
              <span className="absolute inset-y-0 left-0 rounded-full bg-sky-400 transition-[width] duration-500" style={{ width: `${Math.max(12, r.progress)}%` }} />
            )}
          </span>
        );
      })}
    </div>
  );
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (on: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={clsx("relative h-5 w-9 shrink-0 rounded-full transition", on ? "bg-gradient-to-r from-brand to-brand-2" : "bg-white/[0.12]")}
    >
      <span className={clsx("absolute top-0.5 size-4 rounded-full bg-white shadow transition-all", on ? "left-[18px]" : "left-0.5")} />
    </button>
  );
}

export function SimTag() {
  return (
    <span
      title="Bản thiết kế: không gọi iNET / cPanel / Google thật"
      className="inline-flex items-center gap-1 rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10.5px] font-semibold text-amber-300"
    >
      Mô phỏng
    </span>
  );
}
