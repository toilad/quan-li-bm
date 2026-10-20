"use client";

import { useState } from "react";
import clsx from "clsx";
import { Check, Loader2, Play } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { allRoots, rootIssue } from "@/lib/domain-mock";
import { previewIssue, runItems, usablePool, type DomainDispatch, type DomainState } from "./use-domain-queue";

type Preview = { blocked: string | null; token: string | null; rows: { row: number; action: string; reason?: string }[] };

/** Owner, 2026-10-20: the only thing to do here is pick the root domains, then Run. Every row whose column B is empty
 * goes, top to bottom, over the picked roots in name order, round and round. Run = the read-only API check, then the
 * run of exactly that plan; the server's write switch and every check still apply — a refusal is shown, never forced. */
export function QuickRun({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ ok: boolean; text: string } | null>(null);
  const roots = allRoots(state.nicks).sort((a, b) => a.root.name.localeCompare(b.root.name));
  const picked = new Set(state.selectedRoots);
  const pool = usablePool(state).map((p) => p.root.name).sort();
  const items = runItems(state);
  const waiting = state.rows.filter((r) => r.status === "idle" && !r.jobId && r.checked && !previewIssue(r, state)).length;
  const active = state.rows.filter((r) => r.status === "queued" || r.status === "running").length;

  const run = async () => {
    setBusy(true);
    setNote(null);
    try {
      const pv = await api.post<Preview>("/api/domains/preview", { items });
      if (pv.blocked || !pv.token) {
        setNote({ ok: false, text: pv.blocked || "Máy chủ không cho chạy lượt này" });
        return;
      }
      const res = await api.post<{ queued: unknown[]; refused: Record<string, string> }>("/api/domains/run", { token: pv.token });
      const refused = Object.values(res.refused);
      const skipped = pv.rows.filter((r) => r.action === "refuse").length;
      setNote({ ok: true, text: `Đang chạy ${res.queued.length} dòng` + (skipped + refused.length ? ` · bỏ qua ${skipped + refused.length}: ${[
        ...pv.rows.filter((r) => r.action === "refuse").map((r) => `dòng ${r.row} — ${r.reason}`), ...refused].slice(0, 3).join("; ")}` : "") });
    } catch (e) {
      setNote({ ok: false, text: errorText(e) });
    } finally {
      setBusy(false);
      dispatch({ type: "sync" });
    }
  };

  return (
    <section className="panel p-5">
      <h2 className="text-[16px] font-semibold">Chọn tên miền gốc</h2>
      <p className="mt-0.5 text-[12.5px] text-fg-muted">
        App tự lấy mọi dòng cột B trống (từ trên xuống) và chia lần lượt cho các miền đã chọn, rồi quay vòng.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {roots.map(({ root, nick }) => {
          const why = rootIssue(root, nick);
          const on = picked.has(root.name);
          return (
            <button
              key={root.name}
              type="button"
              disabled={!!why && !on}
              title={why ?? `${nick.name} · ${nick.ip}`}
              onClick={() => dispatch({ type: "pickRoots", roots: [root.name], on: !on })}
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 font-mono text-[12.5px] transition",
                on ? "border-emerald-400/60 bg-emerald-500/15 text-emerald-100" : "border-line text-fg-muted hover:border-line-strong hover:text-fg",
                why && !on && "cursor-not-allowed opacity-40",
              )}
            >
              {on && <Check className="size-3.5" />}
              {root.name}
            </button>
          );
        })}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={run}
          disabled={busy || !items.length || !pool.length}
          className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-5 py-2.5 text-[14px] font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
          Chạy {items.length} dòng
        </button>
        <span className="text-[12.5px] text-fg-muted">
          {pool.length
            ? <>{waiting} dòng cột B trống · {pool.join(" → ")} → quay vòng{waiting > items.length ? ` · lượt này ${items.length} dòng đầu, lượt sau làm tiếp` : ""}</>
            : "Bấm chọn ít nhất một miền gốc"}
          {active > 0 && <> · đang chạy {active} dòng</>}
        </span>
      </div>
      {note && <p className={clsx("mt-2 text-[12.5px]", note.ok ? "text-emerald-200" : "text-amber-200")}>{note.text}</p>}
    </section>
  );
}
