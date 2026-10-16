"use client";

import clsx from "clsx";
import { useState } from "react";
import { Globe2, RotateCcw, AlertCircle, Wand2, Hand, Undo2, Lock, ExternalLink } from "lucide-react";
import { TEMPLATES, TEMPLATE_BY_ID } from "@/lib/templates";
import { WEB_STEPS, type WebStatus } from "@/lib/web-mock";
import { WebStatusChip, WebStepBar } from "./web-ui";
import { templateEditable, webIssue, type WebDispatch, type WebState } from "./use-web-queue";

const TABS: { key: string; label: string; match: WebStatus[] }[] = [
  { key: "all", label: "Tất cả", match: [] },
  { key: "idle", label: "Chưa chạy", match: ["idle"] },
  { key: "run", label: "Đang dựng", match: ["queued", "running"] },
  { key: "done", label: "Đã ghi C", match: ["done"] },
  { key: "err", label: "Lỗi / xung đột", match: ["failed", "conflict"] },
];

export function WebTable({ state, dispatch }: { state: WebState; dispatch: WebDispatch }) {
  const [tab, setTab] = useState("all");
  const t = TABS.find((x) => x.key === tab)!;
  const rows = state.rows.filter((r) => !t.match.length || t.match.includes(r.status));
  const selectable = rows.filter((r) => r.status === "idle" && !webIssue(r));
  const allChecked = selectable.length > 0 && selectable.every((r) => r.checked);

  return (
    <section className="panel flex min-h-0 flex-col p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-emerald-500/15 text-emerald-200"><Globe2 className="size-5" /></span>
          <div>
            <h2 className="text-[16px] font-semibold">Dòng cần dựng website</h2>
            <p className="text-[12.5px] text-fg-muted">Chỉ dòng có miền ở cột B và cột C trống · B chỉ đọc · C ghi khi HTTPS chạy thật</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-ink-850/60 p-1">
          {TABS.map((x) => {
            const n = x.match.length ? state.rows.filter((r) => x.match.includes(r.status)).length : state.rows.length;
            return (
              <button key={x.key} onClick={() => setTab(x.key)} className={clsx("rounded-lg px-2.5 py-1 text-[12px] font-medium", tab === x.key ? "bg-white/[0.08] text-fg" : "text-fg-muted hover:text-fg")}>
                {x.label}<span className={clsx("ml-1", x.key === "err" && n ? "text-rose-300" : "text-fg-subtle")}>{n}</span>
              </button>
            );
          })}
        </div>
      </header>

      <div className="scroll-thin mt-4 overflow-x-auto">
        <table className="w-full min-w-[980px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
              <th className="w-9 py-3 pl-2 pr-2">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={() => dispatch({ type: "checkAll", rows: selectable.map((r) => r.row), on: !allChecked })}
                  aria-label="Chọn tất cả dòng chưa chạy"
                  className="size-4 accent-[#4f7cff]"
                />
              </th>
              <th className="py-3 font-medium">Doanh nghiệp · ngành</th>
              <th className="py-3 font-medium">Miền (B) · hosting</th>
              <th className="py-3 font-medium">Mẫu website</th>
              <th className="py-3 font-medium">Tiến trình</th>
              <th className="w-24 py-3" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const issue = webIssue(r);
              const tpl = TEMPLATE_BY_ID[r.templateId];
              const editable = templateEditable(r);
              return (
                <tr
                  key={r.row}
                  onClick={() => dispatch({ type: "select", row: r.row })}
                  className={clsx("cursor-pointer border-b border-line/60 align-top transition-colors hover:bg-white/[0.025]", state.selected === r.row && "bg-brand/[0.07]")}
                >
                  <td className="py-3 pl-2 pr-2" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={r.checked}
                      disabled={r.status !== "idle" || !!issue}
                      onChange={(e) => dispatch({ type: "check", row: r.row, on: e.target.checked })}
                      aria-label={`Chọn ${r.company.A}`}
                      className="size-4 accent-[#4f7cff] disabled:opacity-30"
                    />
                  </td>
                  <td className="max-w-[230px] py-3 pr-3">
                    <div className="truncate font-medium">{r.company.A}</div>
                    <div className="mt-0.5 text-[11.5px] text-fg-subtle">
                      <span className="font-mono text-fg-muted">#{r.row}</span> · {r.detection.template.group}
                    </div>
                    <div className={clsx("mt-0.5 text-[11px]", r.detection.keyword ? "text-fg-subtle" : "text-amber-200/85")}>
                      {r.detection.keyword ? <>Nhận diện từ “<span className="font-mono">{r.detection.keyword}</span>”</> : "Không khớp ngành — mặc định, nên xem lại"}
                    </div>
                  </td>
                  <td className="max-w-[260px] py-3 pr-3">
                    <div className="truncate font-mono text-[12.5px]">{r.domain}</div>
                    <div className="mt-0.5 text-[11px] text-fg-subtle">
                      {r.host ? <>{r.host.nick.name} · <span className="font-mono">{r.host.nick.ip}</span></> : <span className="text-rose-300">Không rõ hosting</span>}
                    </div>
                    {issue && r.status === "idle" && <div className="mt-1 flex items-start gap-1 text-[11px] text-rose-300"><AlertCircle className="mt-px size-3 shrink-0" /> {issue}</div>}
                  </td>
                  <td className="py-3 pr-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1.5">
                      <span className="size-3 shrink-0 rounded-sm" style={{ background: tpl.primary }} />
                      <select
                        value={r.templateId}
                        disabled={!editable}
                        onChange={(e) => dispatch({ type: "template", rows: [r.row], id: e.target.value })}
                        aria-label={`Mẫu cho dòng ${r.row}`}
                        title={r.uploaded ? "Đã upload — đổi mẫu sẽ cần dựng lại, làm ở lượt sau" : undefined}
                        className="h-8 max-w-[200px] rounded-lg border border-line bg-ink-850 px-2 text-[12.5px] outline-none focus:border-brand/60 disabled:opacity-60"
                      >
                        {TEMPLATES.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
                      </select>
                      {!editable && <Lock className="size-3 text-fg-subtle" aria-label="Đã khoá mẫu" />}
                    </div>
                    <div className="mt-1 flex items-center gap-1 text-[11px]">
                      {r.templateSource === "auto" ? (
                        <span className="inline-flex items-center gap-1 text-sky-300/90"><Wand2 className="size-3" /> Tự nhận diện</span>
                      ) : (
                        <>
                          <span className="inline-flex items-center gap-1 text-amber-200/85"><Hand className="size-3" /> Chọn tay</span>
                          {editable && (
                            <button onClick={() => dispatch({ type: "resetTemplate", row: r.row })} className="ml-1 inline-flex items-center gap-0.5 text-fg-subtle hover:text-fg" title={`Về mẫu nhận diện: ${r.detection.template.name}`}>
                              <Undo2 className="size-3" /> về tự động
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                  <td className="py-3 pr-3">
                    <WebStatusChip status={r.status} />
                    <div className="mt-2"><WebStepBar r={r} /></div>
                    <div className="mt-1 max-w-[230px] truncate text-[11px] text-fg-subtle">
                      {r.status === "running" || r.status === "failed" ? `${r.step + 1}/${WEB_STEPS.length} · ${WEB_STEPS[r.step]}` : r.status === "done" ? (
                        <span className="inline-flex items-center gap-1 text-emerald-300/90"><ExternalLink className="size-3" /> {r.writtenC}</span>
                      ) : ""}
                    </div>
                    {r.error && <p className={clsx("mt-1 line-clamp-2 max-w-[250px] text-[11px]", r.status === "conflict" ? "text-amber-200/90" : "text-rose-300/90")}>{r.error}</p>}
                  </td>
                  <td className="py-3 pr-2 text-right" onClick={(e) => e.stopPropagation()}>
                    {r.status === "failed" && (
                      <button onClick={() => dispatch({ type: "retry", row: r.row })} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-medium text-sky-300 hover:bg-sky-400/10">
                        <RotateCcw className="size-3.5" /> Thử lại
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="py-10 text-center text-fg-subtle">Không có dòng nào.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
