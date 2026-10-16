"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { FileText, Search, RotateCcw, X, ScanLine } from "lucide-react";
import { PROCESS_STEPS, SAVE_STEPS, type PdfFile, type PdfStatus } from "@/lib/pdf-mock";
import { PdfStatusChip } from "./status";
import type { QueueDispatch } from "./use-pdf-queue";

type Tab = { key: string; label: string; match: PdfStatus[] };

const TABS: Tab[] = [
  { key: "all", label: "Tất cả", match: [] },
  { key: "wait", label: "Chờ", match: ["queued"] },
  { key: "run", label: "Đang xử lý", match: ["processing", "saving"] },
  { key: "review", label: "Cần kiểm tra", match: ["review"] },
  { key: "ok", label: "Thành công", match: ["saved"] },
  { key: "err", label: "Thất bại", match: ["failed", "duplicate"] },
];

export function FileQueue({
  files, selectedId, dispatch,
}: {
  files: PdfFile[];
  selectedId: string | null;
  dispatch: QueueDispatch;
}) {
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");

  const visible = useMemo(() => {
    const t = TABS.find((x) => x.key === tab)!;
    return files
      .filter((f) => !t.match.length || t.match.includes(f.status))
      .filter((f) => !q || (f.name + " " + (f.fields?.A.value ?? "")).toLowerCase().includes(q.toLowerCase()));
  }, [files, tab, q]);

  return (
    <section className="panel flex max-h-[860px] min-h-0 flex-col self-start p-4 min-[1600px]:self-stretch">
      <header className="mb-3 flex items-center justify-between px-1">
        <h2 className="text-[15px] font-semibold">Danh sách PDF</h2>
        <span className="text-[12px] text-fg-subtle">{files.length} file</span>
      </header>

      <label className="mb-3 flex h-9 items-center gap-2 rounded-xl border border-line bg-ink-850/70 px-3 focus-within:border-brand/60">
        <Search className="size-4 text-fg-subtle" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm tên file, công ty…"
          className="w-full bg-transparent text-[12.5px] outline-none placeholder:text-fg-subtle"
        />
      </label>

      <div className="mb-3 flex flex-wrap gap-1">
        {TABS.map((t) => {
          const n = t.match.length ? files.filter((f) => t.match.includes(f.status)).length : files.length;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={clsx(
                "rounded-lg px-2 py-1 text-[11.5px] font-medium transition",
                tab === t.key ? "bg-white/[0.09] text-fg" : "text-fg-muted hover:bg-white/[0.04] hover:text-fg",
              )}
            >
              {t.label}
              <span className={clsx("ml-1", t.key === "err" && n > 0 ? "text-rose-300" : t.key === "review" && n > 0 ? "text-amber-300" : "text-fg-subtle")}>
                {n}
              </span>
            </button>
          );
        })}
      </div>

      <ul className="scroll-thin -mx-1 min-h-0 flex-1 space-y-1.5 overflow-y-auto px-1">
        {visible.map((f) => (
          <li key={f.id}>
            <div
              role="button"
              tabIndex={0}
              onClick={() => dispatch({ type: "select", id: f.id })}
              onKeyDown={(e) => e.key === "Enter" && dispatch({ type: "select", id: f.id })}
              className={clsx(
                "group w-full cursor-pointer rounded-xl border p-3 text-left transition",
                selectedId === f.id
                  ? "border-brand/50 bg-brand/[0.09] shadow-[inset_3px_0_0_#4f7cff]"
                  : "border-transparent bg-ink-850/50 hover:border-line hover:bg-ink-850",
              )}
            >
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-rose-500/10 text-rose-300">
                  {f.textLayer ? <FileText className="size-4" /> : <ScanLine className="size-4" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12.5px] font-medium" title={f.name}>
                    {f.name}
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-fg-subtle">
                    {f.fields?.A.value || (f.local ? "File trên máy · chưa đọc" : "—")} · {fmtSize(f.sizeKb)}
                    {f.pages > 0 && ` · ${f.pages} trang`}
                  </div>
                </div>
                {["queued", "failed", "duplicate"].includes(f.status) && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      dispatch({ type: "remove", id: f.id });
                    }}
                    aria-label={`Bỏ ${f.name} khỏi danh sách`}
                    className="grid size-6 place-items-center rounded-md text-fg-subtle opacity-0 transition hover:bg-white/[0.08] hover:text-fg group-hover:opacity-100"
                  >
                    <X className="size-3.5" />
                  </button>
                )}
              </div>

              <div className="mt-2 flex items-center justify-between gap-2">
                <PdfStatusChip status={f.status} />
                {f.status === "saved" && <span className="font-mono text-[11px] text-emerald-300/80">Dòng #{f.sheetRow}</span>}
                {f.status === "failed" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      dispatch({ type: "retry", id: f.id });
                    }}
                    className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-sky-300 hover:bg-sky-400/10"
                  >
                    <RotateCcw className="size-3" /> Thử lại
                  </button>
                )}
                {f.status === "duplicate" && f.duplicateOf && (
                  <span className="truncate text-[11px] text-orange-300/80">
                    {f.duplicateOf.row ? `= dòng #${f.duplicateOf.row}` : "trùng file"}
                  </span>
                )}
              </div>

              {(f.status === "processing" || f.status === "saving") && (
                <div className="mt-2">
                  <div className="mb-1 flex justify-between text-[10.5px] text-fg-subtle">
                    <span>
                      {(f.status === "processing" ? PROCESS_STEPS : SAVE_STEPS)[f.step]}
                    </span>
                    <span>
                      {f.step + 1}/{(f.status === "processing" ? PROCESS_STEPS : SAVE_STEPS).length}
                    </span>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className={clsx(
                        "h-full rounded-full transition-[width] duration-500",
                        f.status === "processing" ? "bg-sky-400" : "bg-violet-400",
                      )}
                      style={{
                        width: `${((f.step + f.progress / 100) / (f.status === "processing" ? PROCESS_STEPS : SAVE_STEPS).length) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              )}
              {f.status === "failed" && f.error && <p className="mt-2 line-clamp-2 text-[11px] text-rose-300/90">{f.error}</p>}
            </div>
          </li>
        ))}
        {visible.length === 0 && <li className="py-10 text-center text-[12.5px] text-fg-subtle">Không có file nào.</li>}
      </ul>
    </section>
  );
}

export const fmtSize = (kb: number) => (kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} KB`);
