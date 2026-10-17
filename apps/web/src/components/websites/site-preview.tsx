"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import clsx from "clsx";
import { X, Lock } from "lucide-react";
import { API_URL } from "@/lib/api";
import { TEMPLATE_BY_ID } from "@/lib/templates";
import type { WebRow } from "@/lib/web-mock";

const PAGES = [
  ["index.html", "Trang chủ"], ["about.html", "Giới thiệu"], ["faq.html", "Hỏi đáp"],
  ["contact.html", "Liên hệ"], ["privacy.html", "Bảo mật"], ["terms.html", "Điều khoản"],
] as const;

/**
 * The real output of the backend renderer (brand_render.py, same design the build will use for this
 * domain) — only the AI-written text is replaced by bracketed placeholders.
 */
export function SitePreview({ r, onClose }: { r: WebRow; onClose: () => void }) {
  const t = TEMPLATE_BY_ID[r.templateId];
  const [page, setPage] = useState<(typeof PAGES)[number][0]>("index.html");
  const c = r.company;
  const src = `${API_URL}/api/websites/preview?${new URLSearchParams({
    template: r.templateId, domain: r.domain || "example.com", company: c.A || "Example Company LLC", phone: c.D || "",
    address: [c.F, c.G, [c.H, c.I].filter(Boolean).join(" ")].filter(Boolean).join(", "), page,
  })}`;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Portal to <body>: panels use backdrop-filter, which would trap a fixed overlay inside them.
  return createPortal(
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 p-6 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Xem trước website">
      <div className="flex h-[90vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-2xl border border-line bg-ink-900 shadow-2xl">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2 rounded-lg bg-ink-850 px-3 py-1.5 font-mono text-[12px] text-fg-muted">
            <Lock className="size-3.5 shrink-0 text-emerald-300" /> <span className="truncate">https://{r.domain || "example.com"}/{page === "index.html" ? "" : page}</span>
          </div>
          <div className="flex flex-wrap gap-1 rounded-lg border border-line bg-ink-850/60 p-0.5">
            {PAGES.map(([f, label]) => (
              <button key={f} onClick={() => setPage(f)} className={clsx("rounded-md px-2 py-1 text-[11.5px] font-medium", page === f ? "bg-white/[0.1] text-fg" : "text-fg-muted hover:text-fg")}>
                {label}
              </button>
            ))}
          </div>
          <span className="hidden text-[11.5px] text-fg-subtle lg:block">Mẫu {t.name} · đúng giao diện sẽ dựng · chữ trong [ ] là phần AI viết</span>
          <button onClick={onClose} aria-label="Đóng xem trước" className="grid size-8 place-items-center rounded-lg text-fg-subtle hover:bg-white/[0.06] hover:text-fg"><X className="size-5" /></button>
        </div>
        <iframe title={`Xem trước ${t.name}`} src={src} className="min-h-0 w-full flex-1 bg-white" sandbox="allow-scripts" />
      </div>
    </div>,
    document.body,
  );
}
