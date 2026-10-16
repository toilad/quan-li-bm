import Link from "next/link";
import clsx from "clsx";
import { History, ArrowRight, FileText, Globe2, MonitorCheck, DatabaseBackup } from "lucide-react";
import { ACTIVITY, type ActivityItem } from "@/lib/mock-data";

const MODULE_ICON = { pdf: FileText, domain: Globe2, web: MonitorCheck, system: DatabaseBackup } as const;

const TONE: Record<ActivityItem["tone"], string> = {
  ok: "bg-emerald-500/15 text-emerald-300",
  error: "bg-rose-500/15 text-rose-300",
  warn: "bg-amber-400/15 text-amber-300",
  info: "bg-sky-500/15 text-sky-300",
};

export function ActivityFeed() {
  return (
    <section className="panel h-full p-5">
      <header className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <History className="size-5 text-sky-300" />
          <h2 className="text-[17px] font-semibold">Hoạt động gần đây</h2>
        </div>
        <Link href="/logs" className="inline-flex items-center gap-1 text-[13px] font-medium text-sky-300 hover:text-sky-200">
          Nhật ký <ArrowRight className="size-4" />
        </Link>
      </header>

      <ol className="relative space-y-3.5 before:absolute before:bottom-2 before:left-[47px] before:top-2 before:w-px before:bg-line">
        {ACTIVITY.slice(0, 6).map((a) => {
          const Icon = MODULE_ICON[a.module];
          return (
            <li key={a.time + a.title} className="relative flex items-start gap-3">
              <span className="w-9 shrink-0 pt-1 text-right font-mono text-[11.5px] text-fg-subtle">{a.time}</span>
              <span className={clsx("relative z-10 grid size-7 shrink-0 place-items-center rounded-lg ring-4 ring-ink-850", TONE[a.tone])}>
                <Icon className="size-3.5" />
              </span>
              <div className="min-w-0">
                <div className="truncate text-[13px] font-medium">{a.title}</div>
                <div className="text-[12px] text-fg-muted">{a.detail}</div>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
