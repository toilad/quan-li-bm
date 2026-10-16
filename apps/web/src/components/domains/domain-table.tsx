"use client";

import { useState } from "react";
import clsx from "clsx";
import { Globe2, RotateCcw, PenLine, Lock, AlertCircle, Hourglass } from "lucide-react";
import { DOMAIN_STEPS, nickOf, type RowStatus } from "@/lib/domain-mock";
import { RowStatusChip, StepBar } from "./ui";
import { labelOf, previewIssue, type DomainDispatch, type DomainState } from "./use-domain-queue";

const TABS: { key: string; label: string; match: RowStatus[] }[] = [
  { key: "all", label: "Tất cả", match: [] },
  { key: "idle", label: "Chưa chạy", match: ["idle"] },
  { key: "run", label: "Hàng đợi / đang tạo", match: ["queued", "running"] },
  { key: "done", label: "Thành công", match: ["done"] },
  { key: "err", label: "Lỗi / xung đột", match: ["failed", "conflict"] },
];

export function DomainTable({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const [tab, setTab] = useState("all");
  const [editing, setEditing] = useState<number | null>(null);
  const t = TABS.find((x) => x.key === tab)!;
  const rows = state.rows.filter((r) => !t.match.length || t.match.includes(r.status));
  const idleVisible = rows.filter((r) => r.status === "idle" && !previewIssue(r, state));
  const allChecked = idleVisible.length > 0 && idleVisible.every((r) => r.checked);

  return (
    <section className="panel flex min-h-0 flex-col p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-emerald-500/15 text-emerald-200">
            <Globe2 className="size-5" />
          </span>
          <div>
            <h2 className="text-[16px] font-semibold">Dòng cần tạo miền</h2>
            <p className="text-[12.5px] text-fg-muted">Chỉ dòng có cột B trống và đủ thông tin · xem trước tên miền trước khi chạy</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-ink-850/60 p-1">
          {TABS.map((x) => {
            const n = x.match.length ? state.rows.filter((r) => x.match.includes(r.status)).length : state.rows.length;
            return (
              <button
                key={x.key}
                onClick={() => setTab(x.key)}
                className={clsx("rounded-lg px-2.5 py-1 text-[12px] font-medium", tab === x.key ? "bg-white/[0.08] text-fg" : "text-fg-muted hover:text-fg")}
              >
                {x.label}
                <span className={clsx("ml-1", x.key === "err" && n ? "text-rose-300" : "text-fg-subtle")}>{n}</span>
              </button>
            );
          })}
        </div>
      </header>

      <div className="scroll-thin mt-4 overflow-x-auto">
        <table className="w-full min-w-[840px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
              <th className="w-9 py-3 pl-2 pr-2">
                <input
                  type="checkbox"
                  checked={allChecked}
                  onChange={() => idleVisible.forEach((r) => dispatch({ type: "check", row: r.row, on: !allChecked }))}
                  aria-label="Chọn tất cả dòng chưa chạy"
                  className="size-4 accent-[#4f7cff]"
                />
              </th>
              <th className="py-3 font-medium">Doanh nghiệp</th>
              <th className="py-3 font-medium">Nick iNET</th>
              <th className="py-3 font-medium">Tên miền dự kiến → cột B</th>
              <th className="py-3 font-medium">Tiến trình</th>
              <th className="w-24 py-3" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const issue = previewIssue(r, state);
              const nick = nickOf(r.nickId, state.nicks);
              const locked = r.dnsCreated || !["idle", "failed"].includes(r.status);
              const waitingQuota = r.status === "queued" && nick.usedToday >= nick.dailyLimit;
              return (
                <tr
                  key={r.row}
                  onClick={() => dispatch({ type: "select", row: r.row })}
                  className={clsx(
                    "cursor-pointer border-b border-line/60 align-top transition-colors hover:bg-white/[0.025]",
                    state.selected === r.row && "bg-brand/[0.07]",
                  )}
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
                  <td className="max-w-[210px] py-3 pr-3">
                    <div className="truncate font-medium">{r.company.A}</div>
                    <div className="mt-0.5 truncate text-[11.5px] text-fg-subtle">
                      <span className="font-mono text-fg-muted">#{r.row}</span> · E: <span className="font-mono">{r.company.E}</span>
                    </div>
                  </td>
                  <td className="py-3 pr-3" onClick={(e) => e.stopPropagation()}>
                    <select
                      value={r.nickId}
                      disabled={locked}
                      onChange={(e) => dispatch({ type: "nick", row: r.row, nickId: e.target.value })}
                      title={r.dnsCreated ? "Đã tạo DNS trên nick này — không đổi được" : undefined}
                      className="h-8 rounded-lg border border-line bg-ink-850 px-2 text-[12.5px] outline-none focus:border-brand/60 disabled:opacity-60"
                      aria-label={`Nick cho dòng ${r.row}`}
                    >
                      {state.nicks.map((x) => (
                        <option key={x.id} value={x.id} disabled={!x.enabled}>
                          {x.name} · {x.root}
                        </option>
                      ))}
                    </select>
                    <div className="mt-1 font-mono text-[11px] text-fg-subtle">→ {nick.ip}</div>
                  </td>
                  <td className="max-w-[290px] py-3 pr-3" onClick={(e) => e.stopPropagation()}>
                    {editing === r.row ? (
                      <div className="flex items-center gap-1">
                        <input
                          autoFocus
                          defaultValue={labelOf(r, state.rule)}
                          onBlur={(e) => {
                            dispatch({ type: "slug", row: r.row, value: e.target.value.trim() });
                            setEditing(null);
                          }}
                          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                          className="h-8 w-40 rounded-lg border border-brand/60 bg-ink-850 px-2 font-mono text-[12px] outline-none"
                          aria-label="Sửa tên miền phụ"
                        />
                        <span className="font-mono text-[12px] text-fg-subtle">.{nick.root}</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <span className="truncate font-mono text-[12.5px]">
                          <span className={clsx(r.status === "done" ? "text-emerald-300" : "text-fg")}>{labelOf(r, state.rule)}</span>
                          <span className="text-fg-subtle">.{nick.root}</span>
                        </span>
                        {locked ? (
                          r.dnsCreated && <Lock className="size-3 shrink-0 text-fg-subtle" aria-label="Đã tạo DNS" />
                        ) : (
                          <button onClick={() => setEditing(r.row)} aria-label="Sửa tên" className="shrink-0 text-fg-subtle hover:text-fg">
                            <PenLine className="size-3.5" />
                          </button>
                        )}
                      </div>
                    )}
                    <div className="mt-1 text-[11px]">
                      {r.status === "done" ? (
                        <span className="text-emerald-300/90">Đã ghi B · C giữ nguyên</span>
                      ) : issue && r.status === "idle" ? (
                        <span className="flex items-center gap-1 text-rose-300"><AlertCircle className="size-3 shrink-0" /> {issue}</span>
                      ) : r.slugOverride !== undefined ? (
                        <span className="text-amber-200/80">Đã sửa tay</span>
                      ) : (
                        <span className="text-fg-subtle">Subdomain · không đăng ký domain mới</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 pr-3">
                    <div className="flex items-center gap-2">
                      <RowStatusChip status={r.status} label={waitingQuota ? "Chờ hạn mức nick" : undefined} />
                    </div>
                    <div className="mt-2"><StepBar r={r} /></div>
                    <div className="mt-1 truncate text-[11px] text-fg-subtle">
                      {r.status === "running" || r.status === "failed"
                        ? `${r.step + 1}/${DOMAIN_STEPS.length} · ${DOMAIN_STEPS[r.step]}`
                        : waitingQuota
                          ? <span className="inline-flex items-center gap-1"><Hourglass className="size-3" /> {nick.name} đã dùng {nick.usedToday}/{nick.dailyLimit} hôm nay</span>
                          : r.status === "done" ? r.writtenB : ""}
                    </div>
                    {r.error && <p className={clsx("mt-1 line-clamp-2 max-w-[260px] text-[11px]", r.status === "conflict" ? "text-amber-200/90" : "text-rose-300/90")}>{r.error}</p>}
                  </td>
                  <td className="py-3 pr-2 text-right" onClick={(e) => e.stopPropagation()}>
                    {r.status === "failed" && (
                      <button
                        onClick={() => dispatch({ type: "retry", row: r.row })}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] font-medium text-sky-300 hover:bg-sky-400/10"
                      >
                        <RotateCcw className="size-3.5" /> Thử lại
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="py-10 text-center text-fg-subtle">Không có dòng nào.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

