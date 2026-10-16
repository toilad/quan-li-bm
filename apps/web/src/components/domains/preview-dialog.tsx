"use client";

import { useEffect } from "react";
import clsx from "clsx";
import { X, Play, AlertCircle, CheckCircle2, Flag, Undo2, Info } from "lucide-react";
import { labelOf, nickOfRow, previewIssue, usablePool, type DomainDispatch, type DomainState } from "./use-domain-queue";
import { RootSelect } from "./root-select";

/** Final check before a run: every domain is visible and editable; blocked rows are skipped, never renamed. */
export function PreviewDialog({ state, dispatch, onClose }: { state: DomainState; dispatch: DomainDispatch; onClose: () => void }) {
  const rows = state.rows.filter((r) => r.checked && r.status === "idle");
  const ok = rows.filter((r) => !previewIssue(r, state));
  const willRun = ok.slice(0, state.batchLimit);
  const overLimit = ok.length - willRun.length;
  const noRoots = !usablePool(state).length;
  const usedRoots = new Set(willRun.map((r) => r.root));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/75 p-6 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Xem trước lượt tạo miền">
      <div className="panel flex max-h-[88vh] w-full max-w-[1100px] flex-col !bg-ink-900">
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div>
            <h2 className="text-[17px] font-semibold">Xem trước lượt tạo miền</h2>
            <p className="mt-0.5 text-[12.5px] text-fg-muted">
              Mỗi công ty được gán vào miền gốc nào, của nick nào, và tên miền phụ dự kiến. Đổi miền gốc trong các miền đã tích chọn hoặc sửa tên tại đây — app không tự đổi tên khi trùng.
            </p>
          </div>
          <button onClick={onClose} aria-label="Đóng" className="grid size-8 place-items-center rounded-lg text-fg-subtle hover:bg-white/[0.06] hover:text-fg">
            <X className="size-5" />
          </button>
        </header>

        <div className="flex flex-wrap gap-2 px-6 pt-4 text-[12px]">
          <Pill cls="text-emerald-300">{willRun.length} dòng sẽ chạy</Pill>
          {rows.length - ok.length > 0 && <Pill cls="text-rose-300">{rows.length - ok.length} bị chặn — bỏ qua</Pill>}
          {overLimit > 0 && <Pill cls="text-amber-300">{overLimit} vượt giới hạn {state.batchLimit} dòng/lượt — để lượt sau</Pill>}
          <Pill cls="text-fg-muted">Dùng {usedRoots.size} miền gốc đã chọn</Pill>
          <Pill cls="text-fg-muted">Ghi cột B khi xong · không ghi C</Pill>
          {noRoots && <Pill cls="text-rose-300">Chưa chọn miền gốc nào — không thể bắt đầu</Pill>}
        </div>

        <div className="scroll-thin min-h-0 flex-1 overflow-auto px-6 py-4">
          <table className="w-full min-w-[860px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
                <th className="py-2.5 font-medium">Doanh nghiệp</th>
                <th className="py-2.5 font-medium">Miền gốc</th>
                <th className="py-2.5 font-medium">Nick · IP</th>
                <th className="py-2.5 font-medium">Tên miền phụ</th>
                <th className="py-2.5 font-medium">Kiểm tra</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const issue = previewIssue(r, state);
                const nick = nickOfRow(r, state.nicks);
                return (
                  <tr key={r.row} className="border-b border-line/60 align-top">
                    <td className="max-w-[240px] py-2.5 pr-3">
                      <div className="truncate font-medium">{r.company.A}</div>
                      <div className="text-[11px] text-fg-subtle">
                        <span className="font-mono">#{r.row}</span> · E: <span className="font-mono">{r.company.E || "—"}</span>
                      </div>
                      {r.flags.length > 0 && (
                        <div className="mt-0.5 flex items-center gap-1 text-[11px] text-amber-200/80"><Flag className="size-3" /> {r.flags.join(" · ")}</div>
                      )}
                    </td>
                    <td className="py-2.5 pr-3">
                      <RootSelect r={r} state={state} dispatch={dispatch} />
                    </td>
                    <td className="py-2.5 pr-3 text-[12px]">
                      <div className="font-medium">{nick?.name ?? "—"}</div>
                      {nick && <div className="font-mono text-[11px] text-fg-subtle">A → {nick.ip}</div>}
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-1">
                        <input
                          key={`${r.row}-${state.rule}-${r.slugOverride ?? ""}`}
                          defaultValue={labelOf(r, state.rule)}
                          onBlur={(e) => e.target.value.trim() !== labelOf(r, state.rule) && dispatch({ type: "slug", row: r.row, value: e.target.value.trim() })}
                          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                          className={clsx(
                            "h-8 w-52 rounded-lg border bg-ink-850 px-2 font-mono text-[12.5px] outline-none focus:border-brand/60",
                            issue ? "border-rose-400/50" : "border-line",
                          )}
                          aria-label={`Tên miền phụ dòng ${r.row}`}
                        />
                        <span className="font-mono text-[12px] text-fg-subtle">.{r.root || "…"}</span>
                        {r.slugOverride !== undefined && (
                          <button onClick={() => dispatch({ type: "resetSlug", row: r.row })} title="Về tên theo quy tắc" className="ml-1 text-fg-subtle hover:text-fg">
                            <Undo2 className="size-3.5" />
                          </button>
                        )}
                      </div>
                      {r.slugOverride !== undefined && <div className="mt-1 text-[11px] text-amber-200/80">Đã sửa tay</div>}
                    </td>
                    <td className="py-2.5">
                      {issue ? (
                        <span className="flex items-start gap-1 text-[12px] text-rose-300"><AlertCircle className="mt-0.5 size-3.5 shrink-0" /> {issue}</span>
                      ) : (
                        <span className="flex items-center gap-1 text-[12px] text-emerald-300"><CheckCircle2 className="size-3.5" /> Sẵn sàng</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-6 py-4">
          <span className="flex items-center gap-1.5 text-[12px] text-fg-subtle">
            <Info className="size-3.5" /> Chạy qua API iNET + cPanel trên server (bản này mô phỏng). Đóng trình duyệt vẫn tiếp tục.
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 text-[13px] text-fg-muted hover:text-fg">Quay lại</button>
            <button
              onClick={() => {
                dispatch({ type: "start" });
                onClose();
              }}
              disabled={!willRun.length || noRoots}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-brand to-brand-2 px-4 py-2 text-[13px] font-semibold text-white hover:brightness-110 disabled:opacity-40"
            >
              <Play className="size-4" /> Xác nhận chạy {willRun.length} dòng
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function Pill({ children, cls }: { children: React.ReactNode; cls: string }) {
  return <span className={clsx("rounded-full border border-line bg-ink-850/70 px-3 py-1 font-medium", cls)}>{children}</span>;
}
