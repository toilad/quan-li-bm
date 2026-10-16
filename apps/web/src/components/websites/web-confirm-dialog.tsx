"use client";

import { useEffect } from "react";
import { X, Play, AlertCircle, CheckCircle2, Info } from "lucide-react";
import { TEMPLATES, TEMPLATE_BY_ID } from "@/lib/templates";
import { CONTENT_RULES, SITE_PAGES } from "@/lib/web-mock";
import { templateEditable, webIssue, type WebDispatch, type WebState } from "./use-web-queue";

/** Final check before a run: company → domain B → hosting → template → pages. */
export function WebConfirmDialog({ state, dispatch, onClose }: { state: WebState; dispatch: WebDispatch; onClose: () => void }) {
  const rows = state.rows.filter((r) => r.checked && r.status === "idle");
  const ok = rows.filter((r) => !webIssue(r));
  const willRun = ok.slice(0, state.batchLimit);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/75 p-6 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Xem trước lượt dựng website">
      <div className="panel flex max-h-[88vh] w-full max-w-[1120px] flex-col !bg-ink-900">
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div>
            <h2 className="text-[17px] font-semibold">Xem trước lượt dựng website</h2>
            <p className="mt-0.5 text-[12.5px] text-fg-muted">Mỗi công ty: miền (B) → hosting → mẫu → {SITE_PAGES.length} trang. Đổi mẫu tại đây nếu cần. C chỉ ghi khi HTTPS chạy thật.</p>
          </div>
          <button onClick={onClose} aria-label="Đóng" className="grid size-8 place-items-center rounded-lg text-fg-subtle hover:bg-white/[0.06] hover:text-fg"><X className="size-5" /></button>
        </header>
        <div className="flex flex-wrap gap-2 px-6 pt-4 text-[12px]">
          <span className="rounded-full border border-line bg-ink-850/70 px-3 py-1 font-medium text-emerald-300">{willRun.length} site sẽ chạy</span>
          {rows.length - ok.length > 0 && <span className="rounded-full border border-line bg-ink-850/70 px-3 py-1 font-medium text-rose-300">{rows.length - ok.length} bị chặn — bỏ qua</span>}
          {ok.length > willRun.length && <span className="rounded-full border border-line bg-ink-850/70 px-3 py-1 font-medium text-amber-300">{ok.length - willRun.length} vượt giới hạn — để lượt sau</span>}
          <span className="rounded-full border border-line bg-ink-850/70 px-3 py-1 font-medium text-fg-muted">AI: {state.provider === "claude" ? "Claude" : "OpenAI"}{state.fallback ? " · có dự phòng" : ""}</span>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-auto px-6 py-4">
          <table className="w-full min-w-[900px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
                <th className="py-2.5 font-medium">Doanh nghiệp</th>
                <th className="py-2.5 font-medium">Miền (B)</th>
                <th className="py-2.5 font-medium">Hosting</th>
                <th className="py-2.5 font-medium">Mẫu</th>
                <th className="py-2.5 font-medium">Kiểm tra</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const issue = webIssue(r);
                return (
                  <tr key={r.row} className="border-b border-line/60 align-top">
                    <td className="max-w-[220px] py-2.5 pr-3"><div className="truncate font-medium">{r.company.A}</div><div className="font-mono text-[11px] text-fg-subtle">#{r.row}</div></td>
                    <td className="py-2.5 pr-3 font-mono text-[12px]">{r.domain}</td>
                    <td className="py-2.5 pr-3 text-[12px]">{r.host ? <>{r.host.nick.name}<div className="font-mono text-[11px] text-fg-subtle">{r.host.nick.ip}</div></> : "—"}</td>
                    <td className="py-2.5 pr-3">
                      <select
                        value={r.templateId}
                        disabled={!templateEditable(r)}
                        onChange={(e) => dispatch({ type: "template", rows: [r.row], id: e.target.value })}
                        aria-label={`Mẫu xem trước dòng ${r.row}`}
                        className="h-8 max-w-[210px] rounded-lg border border-line bg-ink-850 px-2 text-[12.5px] outline-none focus:border-brand/60"
                      >
                        {TEMPLATES.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                      <div className="mt-1 text-[11px] text-fg-subtle">{r.templateSource === "auto" ? "Tự nhận diện" : `Chọn tay · nhận diện: ${TEMPLATE_BY_ID[r.detection.template.id].name}`}</div>
                    </td>
                    <td className="py-2.5">
                      {issue ? <span className="flex items-start gap-1 text-[12px] text-rose-300"><AlertCircle className="mt-0.5 size-3.5 shrink-0" /> {issue}</span> : <span className="flex items-center gap-1 text-[12px] text-emerald-300"><CheckCircle2 className="size-3.5" /> Sẵn sàng</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="mt-4 rounded-xl border border-line bg-ink-850/50 p-3.5 text-[12px] text-fg-muted">
            <div className="mb-1.5 font-semibold text-fg">Quy tắc nội dung AI</div>
            <ul className="list-disc space-y-0.5 pl-5">{CONTENT_RULES.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        </div>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-6 py-4">
          <span className="flex items-center gap-1.5 text-[12px] text-fg-subtle"><Info className="size-3.5" /> Chạy qua AI API + cPanel API trên server (bản này mô phỏng). Không điều khiển trình duyệt.</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 text-[13px] text-fg-muted hover:text-fg">Quay lại</button>
            <button
              onClick={() => { dispatch({ type: "start" }); onClose(); }}
              disabled={!willRun.length}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-brand to-brand-2 px-4 py-2 text-[13px] font-semibold text-white hover:brightness-110 disabled:opacity-40"
            >
              <Play className="size-4" /> Xác nhận chạy {willRun.length} site
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
