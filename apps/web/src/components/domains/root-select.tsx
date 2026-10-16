"use client";

import { usablePool, type DomainDispatch, type DomainState } from "./use-domain-queue";
import type { DomainRow } from "@/lib/domain-mock";

/** Root domain of one row — only ticked, usable roots are offered, grouped by the nick that owns them. */
export function RootSelect({ r, state, dispatch, disabled }: { r: DomainRow; state: DomainState; dispatch: DomainDispatch; disabled?: boolean }) {
  const pool = usablePool(state);
  const inPool = pool.some((p) => p.root.name === r.root);
  return (
    <select
      value={r.root}
      disabled={disabled}
      onChange={(e) => dispatch({ type: "root", row: r.row, root: e.target.value })}
      title={r.dnsCreated ? "Đã tạo DNS trên miền này — không đổi được" : undefined}
      className="h-8 max-w-[220px] rounded-lg border border-line bg-ink-850 px-2 font-mono text-[12px] outline-none focus:border-brand/60 disabled:opacity-60"
      aria-label={`Miền gốc cho dòng ${r.row}`}
    >
      {!inPool && <option value={r.root} disabled>{r.root ? `${r.root} (chưa chọn)` : "— chưa gán —"}</option>}
      {state.nicks.map((n) => {
        const mine = pool.filter((p) => p.nick.id === n.id);
        return mine.length ? (
          <optgroup key={n.id} label={`${n.name} · ${n.ip}`}>
            {mine.map((p) => <option key={p.root.name} value={p.root.name}>{p.root.name}</option>)}
          </optgroup>
        ) : null;
      })}
    </select>
  );
}
