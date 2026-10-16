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
            <HomeLayout r={r} />
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

const INTRO = "Đoạn giới thiệu ngắn do AI viết theo ngành — không có giải thưởng, khách hàng hay số liệu tự bịa.";
const SERVICE = "Mô tả chung theo ngành, không hứa hẹn kết quả.";

/** Home page per template: each of the 6 legacy hero layouts gets its own structure, in the template's palette. */
function HomeLayout({ r }: { r: WebRow }) {
  const t = TEMPLATE_BY_ID[r.templateId];
  const Icon = TEMPLATE_ICONS[t.icon];
  const name = r.company.A;
  const photo = (cls = "aspect-[4/3] rounded-2xl") => (
    <div className={clsx("grid place-items-center", cls)} style={{ background: `linear-gradient(135deg, ${t.primary}, ${t.accent})` }}>
      <div className="text-center text-white/90">
        <Icon className="mx-auto size-14" strokeWidth={1.4} />
        <div className="mt-2 text-[12px]">Ảnh: {t.photoKeywords.join(", ")}</div>
      </div>
    </div>
  );
  const ctas = (
    <div className="mt-5 flex gap-3">
      <span className="rounded-lg px-4 py-2 text-[13px] font-semibold text-white" style={{ background: t.primary }}>Liên hệ</span>
      <span className="rounded-lg border px-4 py-2 text-[13px] font-semibold" style={{ borderColor: t.primary, color: t.primary }}>Dịch vụ</span>
    </div>
  );
  const text = (
    <div>
      <div className="text-[12px] font-semibold uppercase tracking-wider" style={{ color: t.primary }}>{t.group}</div>
      <h1 className="mt-2 text-[32px] font-bold leading-tight">{name}</h1>
      <p className="mt-3 italic text-slate-500">{INTRO}</p>
      {ctas}
    </div>
  );
  const cards = (variant: "boxed" | "list" | "accent") => (
    <section className={clsx("px-8 py-10", variant === "list" ? "space-y-3" : "grid gap-4 md:grid-cols-3")}>
      {[1, 2, 3].map((i) =>
        variant === "list" ? (
          <div key={i} className="flex items-start gap-4 border-b border-slate-200 pb-3">
            <span className="font-mono text-[22px] font-bold" style={{ color: t.primary }}>0{i}</span>
            <div><div className="font-semibold">Dịch vụ {i}</div><p className="text-[13px] italic text-slate-500">{SERVICE}</p></div>
          </div>
        ) : (
          <div key={i} className="rounded-xl p-5" style={variant === "accent" ? { background: `${t.accent}33` } : { border: "1px solid #e2e8f0" }}>
            <div className="mb-3 size-8 rounded-lg" style={{ background: variant === "accent" ? t.primary : `${t.accent}88` }} />
            <div className="font-semibold">Dịch vụ {i}</div>
            <p className="mt-1 text-[13px] italic text-slate-500">{SERVICE}</p>
          </div>
        ),
      )}
    </section>
  );

  switch (t.hero) {
    case "centered":
      return (
        <>
          <section className="px-8 py-16 text-center" style={{ background: `linear-gradient(180deg, ${t.primary}, ${t.accent})` }}>
            <Icon className="mx-auto size-12 text-white/90" strokeWidth={1.4} />
            <h1 className="mt-4 text-[36px] font-bold text-white">{name}</h1>
            <p className="mx-auto mt-3 max-w-xl italic text-white/85">{INTRO}</p>
            <span className="mt-6 inline-block rounded-full bg-white px-5 py-2 text-[13px] font-semibold" style={{ color: t.primary }}>Liên hệ</span>
          </section>
          {cards("accent")}
        </>
      );
    case "split-right":
      return (
        <>
          <section className="grid items-center gap-8 px-8 py-12 md:grid-cols-2">{photo()}{text}</section>
          {cards("boxed")}
        </>
      );
    case "minimal":
      return (
        <>
          <section className="border-b border-slate-200 px-8 py-14">
            <h1 className="max-w-3xl text-[40px] font-light leading-tight">{name}</h1>
            <div className="mt-3 h-1 w-16 rounded-full" style={{ background: t.primary }} />
            <p className="mt-4 max-w-2xl italic text-slate-500">{INTRO}</p>
          </section>
          {cards("list")}
        </>
      );
    case "stacked-cards":
      return (
        <>
          <section className="grid items-center gap-8 px-8 py-12 md:grid-cols-[1.1fr_1fr]" style={{ background: `${t.accent}22` }}>
            {text}
            <div className="relative">
              <div className="absolute inset-0 translate-x-3 translate-y-3 rotate-3 rounded-2xl opacity-50" style={{ background: t.accent }} />
              <div className="relative">{photo()}</div>
            </div>
          </section>
          {cards("accent")}
        </>
      );
    case "image-banner":
      return (
        <>
          <section className="relative">
            {photo("h-[300px] rounded-none")}
            <div className="absolute inset-0 flex flex-col items-start justify-end bg-gradient-to-t from-black/60 to-transparent px-8 pb-8">
              <h1 className="text-[34px] font-bold text-white">{name}</h1>
              <p className="mt-2 max-w-xl italic text-white/85">{INTRO}</p>
            </div>
          </section>
          {cards("boxed")}
        </>
      );
    default: // split-left
      return (
        <>
          <section className="grid items-center gap-8 px-8 py-12 md:grid-cols-2" style={{ background: `linear-gradient(135deg, ${t.primary}14, ${t.accent}33)` }}>{text}{photo()}</section>
          {cards("boxed")}
        </>
      );
  }
}
