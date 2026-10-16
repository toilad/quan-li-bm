"use client";

import { useState } from "react";
import clsx from "clsx";
import { CheckCircle2, Circle, Loader2, XCircle, AlertTriangle, RotateCcw, Server, Info, FileText, Lock, ArrowRight, Boxes } from "lucide-react";
import { DNS_HOST_LABEL, DOMAIN_STEPS, findRoot, type Orphan } from "@/lib/domain-mock";
import { RowStatusChip, stepState } from "./ui";
import { fqdnOf, labelOf, type DomainDispatch, type DomainState } from "./use-domain-queue";

export function RowDetail({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const r = state.rows.find((x) => x.row === state.selected) ?? state.rows.find((x) => x.status === "running") ?? state.rows[0];
  if (!r) return <section className="panel p-6 text-[13px] text-fg-subtle">Không có dòng nào.</section>;
  const ref = findRoot(r.root, state.nicks);
  const label = labelOf(r, state.rule);
  const fqdn = fqdnOf(r, state);

  return (
    <section className="panel flex min-h-0 flex-col">
      <header className="border-b border-line px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold">{r.company.A}</div>
            <div className="text-[12px] text-fg-subtle">
              Dòng <span className="font-mono text-fg-muted">#{r.row}</span> · {r.company.G}, {r.company.H}
            </div>
          </div>
          <RowStatusChip status={r.status} />
        </div>
      </header>

      <div className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/[0.05] p-4">
          <div className="text-[11px] font-medium uppercase tracking-wide text-fg-subtle">Tên miền sẽ tạo</div>
          <div className="mt-1 break-all font-mono text-[17px] font-semibold">
            <span className="text-emerald-200">{label}</span>
            <span className="text-fg-muted">.{r.root || "…"}</span>
          </div>
          <div className="mt-2 flex items-start gap-1.5 text-[11.5px] text-fg-muted">
            <Info className="mt-px size-3.5 shrink-0 text-sky-300" />
            <span>
              {ref ? <>Miền phụ (subdomain) của <b className="text-fg">{r.root}</b> — miền gốc đã có sẵn trên nick {ref.nick.name}. </> : "Chưa gán miền gốc — tích chọn miền ở bảng “Miền gốc dùng để tạo miền phụ”. "}Không đăng ký domain mới, không phát sinh phí đăng ký.
            </span>
          </div>
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
          <dt className="text-fg-subtle">Nick iNET</dt>
          <dd>{ref ? `${ref.nick.name} · miền gốc ${r.root}` : "—"}</dd>
          <dt className="text-fg-subtle">Bản ghi DNS</dt>
          <dd>{ref ? <><span className="font-mono">A {label} → {ref.nick.ip}</span><span className="block text-[11px] text-fg-subtle">{DNS_HOST_LABEL[ref.root.dnsHost]}</span></> : "—"}</dd>
          <dt className="text-fg-subtle">cPanel</dt>
          <dd className="font-mono">{ref?.nick.cpanelHost ?? "—"}</dd>
          <dt className="text-fg-subtle">Thư mục web</dt>
          <dd className="truncate font-mono" title={`/public_html/${fqdn}`}>/public_html/{fqdn}</dd>
          <dt className="text-fg-subtle">Phôi</dt>
          <dd>
            <a href={r.company.K} onClick={(e) => e.preventDefault()} className="inline-flex items-center gap-1 text-rose-200 hover:underline">
              <FileText className="size-3.5" /> Xem phôi (K)
            </a>
          </dd>
        </dl>

        <div>
          <div className="mb-2 text-[12.5px] font-semibold">Các bước</div>
          <ol className="space-y-2">
            {DOMAIN_STEPS.map((s, i) => {
              const st = stepState(r, i);
              return (
                <li key={s} className="flex items-center gap-2.5 text-[12.5px]">
                  {st === "done" ? <CheckCircle2 className="size-4 text-emerald-400" />
                    : st === "run" ? <Loader2 className="size-4 animate-spin text-sky-300" />
                      : st === "fail" ? <XCircle className="size-4 text-rose-400" />
                        : st === "warn" ? <AlertTriangle className="size-4 text-amber-300" />
                          : <Circle className="size-4 text-fg-subtle/50" />}
                  <span className={clsx(st === "todo" ? "text-fg-subtle" : st === "fail" ? "text-rose-300" : st === "warn" ? "text-amber-200" : "text-fg")}>{s}</span>
                  {i === 1 && r.dnsCreated && <span className="ml-auto text-[10.5px] text-emerald-300/80">đã tạo</span>}
                  {i === 2 && r.hostCreated && <span className="ml-auto text-[10.5px] text-emerald-300/80">đã tạo</span>}
                </li>
              );
            })}
          </ol>
          {r.dnsCreated && !r.hostCreated && r.status === "failed" && (
            <p className="mt-2.5 rounded-lg bg-amber-400/10 px-3 py-2 text-[11.5px] text-amber-200">
              Mới tạo bản ghi DNS, miền chưa có trên hosting — chưa coi là tạo miền thành công, B chưa ghi.
            </p>
          )}
        </div>

        {r.error && (
          <div className={clsx("rounded-xl border p-3.5 text-[12px]", r.status === "conflict" ? "border-amber-400/30 bg-amber-400/[0.07] text-amber-100" : "border-rose-400/30 bg-rose-500/[0.08] text-rose-100")}>
            {r.error}
            {r.status === "failed" && (
              <button
                onClick={() => dispatch({ type: "retry", row: r.row })}
                className="mt-2.5 flex items-center gap-1.5 rounded-lg bg-white/[0.08] px-2.5 py-1 font-medium text-fg hover:bg-white/[0.13]"
              >
                <RotateCcw className="size-3.5" /> Thử lại từ bước lỗi
              </button>
            )}
          </div>
        )}

        {r.orphan && <OrphanCard row={r.row} orphan={r.orphan} dispatch={dispatch} />}

        <div className="rounded-xl border border-line bg-ink-850/50 p-4 text-[12px]">
          <div className="mb-2 flex items-center gap-2 font-semibold"><Server className="size-4 text-sky-300" /> Ghi Google Sheet</div>
          <div className="flex items-center gap-2">
            <span className="grid size-5 place-items-center rounded bg-brand/20 font-mono text-[10.5px] font-bold text-sky-200">B</span>
            <span className="text-fg-subtle">trống</span>
            <ArrowRight className="size-3.5 text-fg-subtle" />
            {r.writtenB ? <span className="font-mono text-emerald-300">{r.writtenB}</span> : <span className="text-fg-subtle">chỉ ghi khi đủ 4 bước trước thành công</span>}
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-fg-subtle">
            <span className="grid size-5 place-items-center rounded bg-white/[0.04] font-mono text-[10.5px] font-bold">C</span>
            <Lock className="size-3" /> Không bao giờ ghi — thuộc module SSL + Tạo web
          </div>
        </div>

        {r.log.length > 0 && (
          <div>
            <div className="mb-2 text-[12.5px] font-semibold">Nhật ký dòng này</div>
            <ol className="space-y-1.5 font-mono text-[11px]">
              {r.log.map((l, i) => (
                <li key={i} className="flex gap-2">
                  <span className="shrink-0 text-fg-subtle">{l.t}</span>
                  <span className={l.tone === "ok" ? "text-emerald-300/90" : l.tone === "err" ? "text-rose-300" : l.tone === "warn" ? "text-amber-200" : "text-fg-muted"}>{l.msg}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </section>
  );
}

/** Resources created for a row whose B cell was taken meanwhile — kept so nothing is lost or duplicated. */
export function OrphanCard({ row, orphan, dispatch }: { row: number; orphan: Orphan; dispatch: DomainDispatch }) {
  const [note, setNote] = useState("");
  return (
    <div className="rounded-xl border border-amber-400/30 bg-amber-400/[0.06] p-4 text-[12px]">
      <div className="mb-2 flex items-center gap-2 font-semibold text-amber-100">
        <Boxes className="size-4" /> Tài nguyên đã tạo nhưng chưa gắn vào Sheet
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        <dt className="text-fg-subtle">Miền</dt>
        <dd className="font-mono">{orphan.fqdn}</dd>
        <dt className="text-fg-subtle">Nick / IP</dt>
        <dd className="font-mono">{orphan.nick} · {orphan.ip}</dd>
        <dt className="text-fg-subtle">Đã tạo</dt>
        <dd>{orphan.dns && "Bản ghi A"}{orphan.dns && orphan.host && " · "}{orphan.host && "Miền trên cPanel"}</dd>
        <dt className="text-fg-subtle">Ô B hiện có</dt>
        <dd className="font-mono text-amber-200">{orphan.foundB}</dd>
        <dt className="text-fg-subtle">Lúc</dt>
        <dd>{orphan.at}</dd>
      </dl>
      <p className="mt-2 text-[11.5px] text-fg-muted">Lưu trong database. Không ghi đè B, không tự xoá — anh quyết định giữ, gắn lại hay gỡ.</p>
      {orphan.resolved ? (
        <p className="mt-2 flex items-center gap-1.5 text-emerald-300"><CheckCircle2 className="size-3.5" /> Đã xử lý: {orphan.resolved}</p>
      ) : (
        <div className="mt-2.5 flex gap-2">
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Ghi chú cách xử lý (bắt buộc)"
            className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-ink-850 px-2.5 outline-none focus:border-brand/60"
            aria-label={`Ghi chú xử lý dòng ${row}`}
          />
          <button
            disabled={!note.trim()}
            onClick={() => dispatch({ type: "resolveOrphan", row, note: note.trim() })}
            className="rounded-lg bg-white/[0.08] px-2.5 font-medium hover:bg-white/[0.13] disabled:opacity-40"
          >
            Đánh dấu đã xử lý
          </button>
        </div>
      )}
    </div>
  );
}