import Link from "next/link";
import { Hourglass, ArrowLeft } from "lucide-react";
import { Topbar } from "./topbar";

/** Stand-in for screens that are designed after the Dashboard is approved. */
export function ScreenPlaceholder({
  title, subtitle, planned,
}: {
  title: string;
  subtitle: string;
  planned: string[];
}) {
  return (
    <>
      <Topbar title={title} subtitle={subtitle} />
      <section className="panel mx-auto mt-10 max-w-2xl p-8">
        <div className="mb-5 flex items-center gap-3">
          <span className="grid size-11 place-items-center rounded-xl bg-violet-500/15 text-violet-200">
            <Hourglass className="size-5" />
          </span>
          <div>
            <h2 className="text-[17px] font-semibold">Thiết kế chi tiết sau khi duyệt Tổng quan</h2>
            <p className="text-[13px] text-fg-muted">Màn hình này sẽ có:</p>
          </div>
        </div>
        <ul className="space-y-2.5 text-[14px] text-fg-muted">
          {planned.map((p) => (
            <li key={p} className="flex gap-2.5">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-gradient-to-r from-brand to-brand-2" />
              {p}
            </li>
          ))}
        </ul>
        <Link href="/" className="mt-7 inline-flex items-center gap-1.5 text-[13px] font-medium text-sky-300 hover:text-sky-200">
          <ArrowLeft className="size-4" /> Về Tổng quan
        </Link>
      </section>
    </>
  );
}
