import Link from "next/link";
import { LayoutTemplate, ArrowRight, Eye } from "lucide-react";
import { TEMPLATES } from "@/lib/templates";
import { COMPANIES } from "@/lib/mock-data";
import { TemplateThumb } from "@/components/templates/template-thumb";

const FEATURED = ["misbah-architecture", "blockskit-digital", "herbal-shop", "corporate-firm"];

export function TemplateShowcase() {
  const groups = new Set(TEMPLATES.map((t) => t.group)).size;
  const usage = (id: string) => COMPANIES.filter((c) => c.template.id === id).length;
  const featured = FEATURED.map((id) => TEMPLATES.find((t) => t.id === id)!);

  return (
    <section className="panel p-5">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-violet-500/15 text-violet-200">
            <LayoutTemplate className="size-5" />
          </span>
          <div>
            <h2 className="text-[17px] font-semibold">Mẫu website</h2>
            <p className="text-[12.5px] text-fg-muted">
              {TEMPLATES.length} mẫu có tên từ app cũ · {groups} nhóm ngành · tự nhận diện theo tên công ty, chọn tay được
            </p>
          </div>
        </div>
        <Link href="/templates" className="inline-flex items-center gap-1 text-[13px] font-medium text-sky-300 hover:text-sky-200">
          Kho mẫu <ArrowRight className="size-4" />
        </Link>
      </header>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {featured.map((t) => (
          <article key={t.id} className="group rounded-2xl border border-line bg-ink-850/60 p-2.5 transition hover:border-line-strong">
            <div className="relative">
              <TemplateThumb t={t} />
              <div className="absolute inset-0 grid place-items-center rounded-xl bg-ink-950/60 opacity-0 transition group-hover:opacity-100">
                <span className="inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-3 py-1.5 text-[12px] font-semibold backdrop-blur">
                  <Eye className="size-3.5" /> Xem trước
                </span>
              </div>
            </div>
            <div className="mt-3 flex items-end justify-between gap-2 px-1 pb-0.5">
              <div className="min-w-0">
                <div title={t.name} className="truncate text-[13.5px] font-semibold">{t.name}</div>
                <div className="text-[11.5px] text-fg-subtle">{t.group}</div>
              </div>
              <span className="shrink-0 rounded-md bg-white/[0.05] px-2 py-0.5 text-[11px] text-fg-muted">
                {usage(t.id)} công ty
              </span>
            </div>
          </article>
        ))}
      </div>

      <div className="mt-5 border-t border-line pt-4">
        <div className="mb-2.5 text-[12px] font-medium text-fg-subtle">Nhóm ngành · số mẫu</div>
        <div className="flex flex-wrap gap-2">
          {[...new Set(TEMPLATES.map((t) => t.group))].map((g) => {
            const inGroup = TEMPLATES.filter((t) => t.group === g);
            return (
              <Link
                key={g}
                href="/templates"
                title={inGroup.map((t) => t.name).join(" · ")}
                className="inline-flex items-center gap-2 rounded-lg border border-line bg-ink-850/60 px-2.5 py-1.5 text-[12px] text-fg-muted transition hover:border-line-strong hover:text-fg"
              >
                <span className="flex -space-x-1">
                  {inGroup.map((t) => (
                    <span key={t.id} className="size-2.5 rounded-full ring-2 ring-ink-850" style={{ background: t.primary }} />
                  ))}
                </span>
                {g}
                <span className="text-fg-subtle">{inGroup.length}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}
