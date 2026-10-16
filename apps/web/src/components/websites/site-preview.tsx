"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { X, Lock, Phone, MapPin } from "lucide-react";
import { TEMPLATE_BY_ID } from "@/lib/templates";
import { SITE_PAGES, sheetFacts, type WebRow } from "@/lib/web-mock";
import { TEMPLATE_ICONS } from "@/components/templates/template-thumb";

/**
 * Approximate preview of the site the builder will produce: the template's
 * palette and hero, the Sheet facts, and placeholder copy where the AI writes.
 * The real renderer replaces this.
 */
export function SitePreview({ r, onClose }: { r: WebRow; onClose: () => void }) {
  const t = TEMPLATE_BY_ID[r.templateId];
  const Icon = TEMPLATE_ICONS[t.icon];
  const [page, setPage] = useState<(typeof SITE_PAGES)[number]>("Trang chủ");
  const c = r.company;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Portal to <body>: panels use backdrop-filter, which would trap a fixed overlay inside them.
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-6 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Xem trước website">
      <div className="flex max-h-[90vh] w-full max-w-[1080px] flex-col overflow-hidden rounded-2xl border border-line bg-ink-900 shadow-2xl">
        <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2 rounded-lg bg-ink-850 px-3 py-1.5 font-mono text-[12px] text-fg-muted">
            <Lock className="size-3.5 shrink-0 text-emerald-300" /> <span className="truncate">https://{r.domain}</span>
          </div>
          <span className="hidden text-[11.5px] text-fg-subtle md:block">Bản xem trước gần đúng · mẫu {t.name} · chữ in nghiêng là phần AI sẽ viết</span>
          <button onClick={onClose} aria-label="Đóng xem trước" className="grid size-8 place-items-center rounded-lg text-fg-subtle hover:bg-white/[0.06] hover:text-fg"><X className="size-5" /></button>
        </div>

        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto bg-white text-slate-800">
          <nav className="flex items-center justify-between border-b border-slate-200 px-8 py-4">
            <div className="flex items-center gap-2 font-bold" style={{ color: t.primary }}>
              <span className="grid size-7 place-items-center rounded-md text-white" style={{ background: t.primary }}><Icon className="size-4" /></span>
              {c.A}
            </div>
            <div className="flex flex-wrap gap-4 text-[13px]">
              {SITE_PAGES.map((p) => (
                <button key={p} onClick={() => setPage(p)} className={clsx("hover:underline", page === p ? "font-semibold" : "text-slate-500")} style={page === p ? { color: t.primary } : undefined}>
                  {p}
                </button>
              ))}
            </div>
          </nav>

          {page === "Trang chủ" ? (
            <>
              <section className="grid items-center gap-8 px-8 py-12 md:grid-cols-2" style={{ background: `linear-gradient(135deg, ${t.primary}14, ${t.accent}33)` }}>
                <div>
                  <div className="text-[12px] font-semibold uppercase tracking-wider" style={{ color: t.primary }}>{t.group}</div>
                  <h1 className="mt-2 text-[32px] font-bold leading-tight">{c.A}</h1>
                  <p className="mt-3 italic text-slate-500">Đoạn giới thiệu ngắn do AI viết theo ngành — không có giải thưởng, khách hàng hay số liệu tự bịa.</p>
                  <div className="mt-5 flex gap-3">
                    <span className="rounded-lg px-4 py-2 text-[13px] font-semibold text-white" style={{ background: t.primary }}>Liên hệ</span>
                    <span className="rounded-lg border px-4 py-2 text-[13px] font-semibold" style={{ borderColor: t.primary, color: t.primary }}>Dịch vụ</span>
                  </div>
                </div>
                <div className="grid aspect-[4/3] place-items-center rounded-2xl" style={{ background: `linear-gradient(135deg, ${t.primary}, ${t.accent})` }}>
                  <div className="text-center text-white/90">
                    <Icon className="mx-auto size-14" strokeWidth={1.4} />
                    <div className="mt-2 text-[12px]">Ảnh: {t.photoKeywords.join(", ")}</div>
                  </div>
                </div>
              </section>
              <section className="grid gap-4 px-8 py-10 md:grid-cols-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="rounded-xl border border-slate-200 p-5">
                    <div className="mb-3 size-8 rounded-lg" style={{ background: `${t.accent}88` }} />
                    <div className="font-semibold">Dịch vụ {i}</div>
                    <p className="mt-1 text-[13px] italic text-slate-500">Mô tả chung theo ngành, không hứa hẹn kết quả.</p>
                  </div>
                ))}
              </section>
            </>
          ) : (
            <section className="px-8 py-12">
              <h1 className="text-[26px] font-bold" style={{ color: t.primary }}>{page}</h1>
              <p className="mt-3 max-w-2xl italic text-slate-500">
                {page === "Liên hệ" ? "Biểu mẫu liên hệ + thông tin bên dưới (chỉ lấy từ Sheet)." : `Nội dung trang “${page}” do AI viết theo cấu trúc JSON cố định, dùng tên doanh nghiệp và địa chỉ từ Sheet.`}
              </p>
            </section>
          )}

          <footer className="grid gap-4 border-t border-slate-200 bg-slate-50 px-8 py-6 text-[13px] md:grid-cols-3">
            {sheetFacts(c).map(([k, v]) => (
              <div key={k}>
                <div className="text-[11px] uppercase tracking-wide text-slate-400">{k}</div>
                <div className="mt-0.5 flex items-center gap-1.5">
                  {k.startsWith("Điện") ? <Phone className="size-3.5" /> : k.startsWith("Địa") ? <MapPin className="size-3.5" /> : null}
                  {v || <span className="text-slate-400">— trống, không tự điền</span>}
                </div>
              </div>
            ))}
          </footer>
        </div>
      </div>
    </div>,
    document.body,
  );
}
