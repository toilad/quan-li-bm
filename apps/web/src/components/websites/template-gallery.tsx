"use client";

import { useState } from "react";
import clsx from "clsx";
import { LayoutTemplate, Check, Eye } from "lucide-react";
import { TEMPLATES, type TemplateGroup } from "@/lib/templates";
import { TemplateThumb } from "@/components/templates/template-thumb";
import { templateEditable, type WebDispatch, type WebState } from "./use-web-queue";
import { SitePreview } from "./site-preview";

/** The 15 legacy templates. Clicking one applies it to the ticked rows (manual choice). */
export function TemplateGallery({ state, dispatch }: { state: WebState; dispatch: WebDispatch }) {
  const groups = ["Tất cả", ...Array.from(new Set(TEMPLATES.map((t) => t.group)))] as ("Tất cả" | TemplateGroup)[];
  const [group, setGroup] = useState<(typeof groups)[number]>("Tất cả");
  const targets = state.rows.filter((r) => r.checked && templateEditable(r));
  const used = (id: string) => state.rows.filter((r) => r.templateId === id).length;
  const list = TEMPLATES.filter((t) => group === "Tất cả" || t.group === group);
  const [previewId, setPreviewId] = useState<string | null>(null);
  // Full-page preview of a template, filled with the selected (or first) row of the Sheet.
  const sample = state.rows.find((r) => r.row === state.selected) ?? state.rows[0];

  return (
    <section className="panel p-5">
      <header className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-fuchsia-500/15 text-fuchsia-200"><LayoutTemplate className="size-5" /></span>
          <div>
            <h2 className="text-[16px] font-semibold">15 mẫu website (từ app cũ)</h2>
            <p className="text-[12.5px] text-fg-muted">
              {targets.length
                ? <>Bấm một mẫu để áp cho <b className="text-fg">{targets.length} dòng đang chọn</b> (thành “chọn tay”).</>
                : "Tích dòng ở bảng bên dưới rồi bấm mẫu để đổi hàng loạt; hoặc đổi từng dòng trong bảng."}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-ink-850/60 p-1">
          {groups.map((g) => (
            <button key={g} onClick={() => setGroup(g)} className={clsx("rounded-lg px-2 py-1 text-[11.5px] font-medium", group === g ? "bg-white/[0.08] text-fg" : "text-fg-muted hover:text-fg")}>
              {g}
            </button>
          ))}
        </div>
      </header>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {list.map((t) => (
          <div key={t.id} className="rounded-xl border border-line bg-ink-850/50">
          <button
            onClick={() => targets.length && dispatch({ type: "template", rows: targets.map((r) => r.row), id: t.id })}
            disabled={!targets.length}
            aria-label={`Áp mẫu ${t.name}`}
            className={clsx("group block w-full rounded-t-xl p-2 text-left transition", targets.length ? "hover:border-brand/50 hover:bg-brand/[0.06]" : "cursor-default")}
          >
            <TemplateThumb t={t} />
            <div className="mt-2 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="truncate text-[12.5px] font-semibold">{t.name}</div>
                <div className="truncate text-[11px] text-fg-subtle">{t.group}</div>
              </div>
              {used(t.id) > 0 && (
                <span className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-white/[0.06] px-1.5 py-0.5 text-[10.5px] text-fg-muted">
                  <Check className="size-3" /> {used(t.id)}
                </span>
              )}
            </div>
            <div className="mt-1 truncate text-[10.5px] text-fg-subtle" title={t.industries.join(", ")}>Từ khoá: {t.industries.slice(0, 4).join(", ")}…</div>
          </button>
          {sample && (
            <button onClick={() => setPreviewId(t.id)} aria-label={`Xem trước mẫu ${t.name}`} className="flex w-full items-center justify-center gap-1 border-t border-line/70 py-1.5 text-[11.5px] font-medium text-fg-muted hover:text-fg">
              <Eye className="size-3.5" /> Xem trước
            </button>
          )}
          </div>
        ))}
      </div>
      {previewId && sample && <SitePreview r={{ ...sample, templateId: previewId }} onClose={() => setPreviewId(null)} />}
    </section>
  );
}
