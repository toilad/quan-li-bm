"use client";

import { useState } from "react";
import clsx from "clsx";
import { CheckCircle2, Circle, Loader2, XCircle, AlertTriangle, RotateCcw, Server, Lock, ArrowRight, Eye, ShieldCheck, Boxes, Wand2, Hand } from "lucide-react";
import { TEMPLATE_BY_ID } from "@/lib/templates";
import { SITE_PAGES, WEB_STEPS } from "@/lib/web-mock";
import { TemplateThumb } from "@/components/templates/template-thumb";
import { WebStatusChip, webStepState } from "./web-ui";
import type { WebDispatch, WebState } from "./use-web-queue";
import { SitePreview } from "./site-preview";

export function WebDetail({ state, dispatch }: { state: WebState; dispatch: WebDispatch }) {
  const r = state.rows.find((x) => x.row === state.selected) ?? state.rows.find((x) => x.status === "running") ?? state.rows[0];
  const [preview, setPreview] = useState(false);
  const [note, setNote] = useState("");
  if (!r) return <section className="panel p-6 text-[13px] text-fg-subtle">Không có dòng nào đủ điều kiện (B có miền, C trống).</section>;
  const t = TEMPLATE_BY_ID[r.templateId];

  return (
    <section className="panel flex min-h-0 flex-col">
      <header className="border-b border-line px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold">{r.company.A}</div>
            <div className="truncate font-mono text-[12px] text-fg-muted">{r.domain}</div>
          </div>
          <WebStatusChip status={r.status} />
        </div>
      </header>

      <div className="scroll-thin min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        <div className="rounded-xl border border-line bg-ink-850/50 p-3">
          <TemplateThumb t={t} />
          <div className="mt-2.5 flex items-start justify-between gap-2">
            <div>
              <div className="text-[13px] font-semibold">{t.name}</div>
              <div className="flex items-center gap-1 text-[11.5px] text-fg-subtle">
                {r.templateSource === "auto" ? <><Wand2 className="size-3 text-sky-300" /> Nhận diện: {r.detection.keyword ? `từ khoá “${r.detection.keyword}”` : "không khớp — mặc định"}</> : <><Hand className="size-3 text-amber-200" /> Chọn tay (nhận diện: {r.detection.template.name})</>}
              </div>
            </div>
            <button onClick={() => setPreview(true)} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-white/[0.07] px-2.5 py-1.5 text-[12px] font-semibold hover:bg-white/[0.11]">
              <Eye className="size-3.5" /> Xem trước
            </button>
          </div>
          <div className="mt-2 text-[11px] text-fg-subtle">{SITE_PAGES.length} trang: {SITE_PAGES.join(" · ")}</div>
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
          <dt className="text-fg-subtle">Hosting</dt>
          <dd>{r.host ? `${r.host.nick.name} · ${r.host.nick.ip}` : <span className="text-rose-300">Không rõ — miền B không thuộc nick nào</span>}</dd>
          <dt className="text-fg-subtle">cPanel</dt>
          <dd className="font-mono">{r.host?.nick.cpanelHost ?? "—"}</dd>
          <dt className="text-fg-subtle">Document root</dt>
          <dd className="min-w-0">
            {r.docRoot
              ? <><span className="block truncate font-mono" title={`~/${r.docRoot}`}>~/{r.docRoot}</span><span className="block text-[11px] text-fg-subtle">đọc từ cPanel: {r.docRootApi}</span></>
              : <span className="text-fg-subtle">Chưa đọc — lấy từ cPanel API trước khi upload, không đoán đường dẫn</span>}
          </dd>
          <dt className="text-fg-subtle">Mẫu đã dựng</dt>
          <dd>{r.builtTemplate ? TEMPLATE_BY_ID[r.builtTemplate].name : <span className="text-fg-subtle">chưa dựng</span>}</dd>
          <dt className="text-fg-subtle">SSL</dt>
          <dd className="flex items-center gap-1">{r.sslIssued ? <><ShieldCheck className="size-3.5 text-emerald-300" /> Đã cấp (AutoSSL)</> : "Chưa cấp — bật qua SSL::start_autossl_check"}</dd>
        </dl>

        <div>
          <div className="mb-2 text-[12.5px] font-semibold">Các bước</div>
          <ol className="space-y-1.5">
            {WEB_STEPS.map((s, i) => {
              const st = webStepState(r, i);
              return (
                <li key={s} className="flex items-center gap-2.5 text-[12.5px]">
                  {st === "done" ? <CheckCircle2 className="size-4 text-emerald-400" /> : st === "run" ? <Loader2 className="size-4 animate-spin text-sky-300" /> : st === "fail" ? <XCircle className="size-4 text-rose-400" /> : st === "warn" ? <AlertTriangle className="size-4 text-amber-300" /> : <Circle className="size-4 text-fg-subtle/50" />}
                  <span className={clsx(st === "todo" ? "text-fg-subtle" : st === "fail" ? "text-rose-300" : st === "warn" ? "text-amber-200" : "text-fg")}>{s}</span>
                </li>
              );
            })}
          </ol>
          {r.uploaded && r.status === "failed" && (
            <p className="mt-2.5 rounded-lg bg-amber-400/10 px-3 py-2 text-[11.5px] text-amber-200">Đã upload nhưng HTTPS chưa chạy — chưa coi là thành công, C chưa ghi. Thử lại sẽ không upload lại.</p>
          )}
        </div>

        {r.error && (
          <div className={clsx("rounded-xl border p-3.5 text-[12px]", r.status === "conflict" ? "border-amber-400/30 bg-amber-400/[0.07] text-amber-100" : "border-rose-400/30 bg-rose-500/[0.08] text-rose-100")}>
            {r.error}
            {r.status === "failed" && (
              <button onClick={() => dispatch({ type: "retry", row: r.row })} className="mt-2.5 flex items-center gap-1.5 rounded-lg bg-white/[0.08] px-2.5 py-1 font-medium text-fg hover:bg-white/[0.13]">
                <RotateCcw className="size-3.5" /> Thử lại từ bước lỗi
              </button>
            )}
          </div>
        )}

        {r.liveNotWritten && (
          <div className="rounded-xl border border-amber-400/30 bg-amber-400/[0.06] p-4 text-[12px]">
            <div className="mb-2 flex items-center gap-2 font-semibold text-amber-100"><Boxes className="size-4" /> Website đang chạy nhưng chưa ghi vào Sheet</div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="text-fg-subtle">Website</dt><dd className="font-mono">{r.liveNotWritten.url}</dd>
              <dt className="text-fg-subtle">Ô C hiện có</dt><dd className="font-mono text-amber-200">{r.liveNotWritten.foundC}</dd>
              <dt className="text-fg-subtle">Lúc</dt><dd>{r.liveNotWritten.at}</dd>
            </dl>
            {r.liveNotWritten.resolved ? (
              <p className="mt-2 flex items-center gap-1.5 text-emerald-300"><CheckCircle2 className="size-3.5" /> Đã xử lý: {r.liveNotWritten.resolved}</p>
            ) : (
              <div className="mt-2.5 flex gap-2">
                <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ghi chú cách xử lý (bắt buộc)" aria-label={`Ghi chú xử lý website dòng ${r.row}`} className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-ink-850 px-2.5 outline-none focus:border-brand/60" />
                <button disabled={!note.trim()} onClick={() => dispatch({ type: "resolveLive", row: r.row, note: note.trim() })} className="rounded-lg bg-white/[0.08] px-2.5 font-medium hover:bg-white/[0.13] disabled:opacity-40">Đánh dấu đã xử lý</button>
              </div>
            )}
          </div>
        )}

        <div className="rounded-xl border border-line bg-ink-850/50 p-4 text-[12px]">
          <div className="mb-2 flex items-center gap-2 font-semibold"><Server className="size-4 text-sky-300" /> Ghi Google Sheet</div>
          <div className="flex items-center gap-2 text-fg-subtle">
            <span className="grid size-5 place-items-center rounded bg-white/[0.04] font-mono text-[10.5px] font-bold">B</span>
            <Lock className="size-3" /> Chỉ đọc — {r.domain}
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="grid size-5 place-items-center rounded bg-brand/20 font-mono text-[10.5px] font-bold text-sky-200">C</span>
            <span className="text-fg-subtle">trống</span>
            <ArrowRight className="size-3.5 text-fg-subtle" />
            {r.writtenC ? <span className="font-mono text-emerald-300">{r.writtenC}</span> : <span className="text-fg-subtle">chỉ ghi khi HTTPS chạy thật và ô C vẫn trống</span>}
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
      {preview && <SitePreview r={r} onClose={() => setPreview(false)} />}
    </section>
  );
}
