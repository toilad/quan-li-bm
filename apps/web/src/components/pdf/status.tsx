import clsx from "clsx";
import { Clock3, Loader2, ScanSearch, UploadCloud, CheckCircle2, XCircle, Copy, type LucideIcon } from "lucide-react";
import type { PdfStatus } from "@/lib/pdf-mock";

export const PDF_STATUS: Record<PdfStatus, { label: string; icon: LucideIcon; cls: string; spin?: boolean }> = {
  queued: { label: "Chờ xử lý", icon: Clock3, cls: "border-indigo-400/25 bg-indigo-400/10 text-indigo-200" },
  processing: { label: "Đang xử lý", icon: Loader2, cls: "border-sky-400/30 bg-sky-400/10 text-sky-300", spin: true },
  review: { label: "Cần kiểm tra", icon: ScanSearch, cls: "border-amber-400/35 bg-amber-400/10 text-amber-300" },
  saving: { label: "Đang lưu", icon: UploadCloud, cls: "border-violet-400/30 bg-violet-400/10 text-violet-300" },
  saved: { label: "Thành công", icon: CheckCircle2, cls: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300" },
  failed: { label: "Thất bại", icon: XCircle, cls: "border-rose-400/35 bg-rose-500/10 text-rose-300" },
  duplicate: { label: "Trùng", icon: Copy, cls: "border-orange-400/35 bg-orange-400/10 text-orange-300" },
};

export function PdfStatusChip({ status, className }: { status: PdfStatus; className?: string }) {
  const s = PDF_STATUS[status];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-[11px] font-semibold",
        s.cls,
        className,
      )}
    >
      <s.icon className={clsx("size-3", s.spin && "animate-spin")} />
      {s.label}
    </span>
  );
}
