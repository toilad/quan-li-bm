"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Globe, Power, FlaskConical, CheckCircle2, AlertCircle } from "lucide-react";
import { api, errorText } from "@/lib/api";

export type WriteOp = "dns" | "host" | "upload" | "ssl";
export type DnsWrite = {
  enabled: boolean; trial_fqdn: string; ops: WriteOp[]; trial_passed: boolean; trial_job: number | null;
  web_trial_passed: boolean; web_trial_job: number | null; changed_at: string | null; locked_reason: string | null; mode: "off" | "trial" | "batch";
  op_labels: Record<WriteOp, string>;
};

export const DNS_MODE_TEXT: Record<DnsWrite["mode"], string> = {
  off: "KHOÁ — không ghi gì thật",
  trial: "Chạy thử — chỉ 1 miền thử",
  batch: "Mở — chạy hàng loạt (vẫn xem trước + xác nhận)",
};

/** Owner-only lock for every real write (iNET A record, cPanel domain, website upload, AutoSSL). Locked until the
 *  owner names a trial name, ticks the allowed operations and opens it; the server checks it before each write. */
export function DnsWriteCard() {
  const [sw, setSw] = useState<DnsWrite | null>(null);
  const [trial, setTrial] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => api.get<DnsWrite>("/api/domains/dns-write").then((d) => { setSw(d); setTrial(d.trial_fqdn); }).catch((e) => setMsg({ ok: false, text: errorText(e) })), []);
  useEffect(() => { load(); }, [load]);

  const put = async (body: Partial<{ enabled: boolean; trial_fqdn: string; ops: WriteOp[] }>, ok: string) => {
    try {
      const d = await api.putJson<DnsWrite>("/api/domains/dns-write", body);
      setSw(d);
      setTrial(d.trial_fqdn);
      setMsg({ ok: true, text: ok });
    } catch (e) {
      setMsg({ ok: false, text: errorText(e) });
    }
  };

  if (!sw) return null;
  const ops = Object.keys(sw.op_labels) as WriteOp[];
  const toggle = (op: WriteOp) => {
    const next = sw.ops.includes(op) ? sw.ops.filter((o) => o !== op) : [...sw.ops, op];
    put({ ops: next }, `${sw.ops.includes(op) ? "Đã bỏ" : "Đã cho phép"}: ${sw.op_labels[op]}`);
  };
  return (
    <section className="panel p-5" aria-label="Ghi thật">
      <header className="mb-4 flex items-start gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-amber-500/15 text-amber-200"><Globe className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[16px] font-semibold">Ghi thật (DNS, hosting, SSL)</h2>
          <p className="text-[12.5px] text-fg-muted">
            Mặc định KHOÁ. Mỗi thao tác ghi thật (bản ghi A trên iNET, tạo miền trên cPanel, tải web lên, chạy AutoSSL) được kiểm tra ở máy chủ ngay trước khi gửi.
            Anh đặt 1 miền thử, tích các thao tác cho phép rồi mở khoá; thành công trên miền thử mới được làm cho miền khác.
          </p>
        </div>
        <span className={clsx("shrink-0 rounded-full border px-3 py-1 text-[12px] font-semibold",
          sw.mode === "off" ? "border-line text-fg-muted" : sw.mode === "trial" ? "border-amber-400/40 text-amber-300" : "border-emerald-400/40 text-emerald-300")}>
          {DNS_MODE_TEXT[sw.mode]}
        </span>
      </header>
      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Thao tác được phép">
        {ops.map((op) => (
          <label key={op} className={clsx("inline-flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-[12.5px]",
            sw.ops.includes(op) ? "border-amber-400/50 text-amber-200" : "border-line text-fg-muted")}>
            <input type="checkbox" checked={sw.ops.includes(op)} onChange={() => toggle(op)} aria-label={sw.op_labels[op]} />
            {sw.op_labels[op]}
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[260px] flex-1 text-[12px]">
          <span className="mb-1 flex items-center gap-1.5 text-fg-muted"><FlaskConical className="size-3.5" /> Miền thử (tên mới dưới miền gốc đã tích)</span>
          <input value={trial} onChange={(e) => setTrial(e.target.value)} placeholder="vd: test.mien-goc-da-tich.com"
            aria-label="Miền thử" className="h-9 w-full rounded-lg border border-line bg-ink-850 px-3 font-mono text-[12.5px] outline-none focus:border-brand/60" />
        </label>
        <button onClick={() => put({ trial_fqdn: trial.trim() }, trial.trim() ? `Đã đặt miền thử ${trial.trim()}` : "Đã bỏ miền thử")}
          className="h-9 rounded-lg border border-line px-3 text-[12.5px] text-fg-muted hover:text-fg">Lưu miền thử</button>
        {sw.enabled ? (
          <button onClick={() => put({ enabled: false }, "Đã KHOÁ ghi thật")}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-rose-400/40 px-3 text-[12.5px] font-semibold text-rose-300 hover:bg-rose-500/10">
            <Power className="size-4" /> Khoá ghi thật
          </button>
        ) : (
          <button onClick={() => put({ enabled: true }, "Đã mở ghi thật — chế độ chạy thử")}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 text-[12.5px] font-semibold text-white hover:brightness-110">
            <Power className="size-4" /> Mở ghi thật
          </button>
        )}
      </div>
      {!sw.enabled && sw.locked_reason && <p className="mt-3 text-[12px] text-fg-muted">{sw.locked_reason}</p>}
      {sw.trial_passed && <p className="mt-3 text-[12px] text-emerald-300">Miền thử đã tạo xong{sw.trial_job ? ` (việc #${sw.trial_job})` : ""}. Đổi miền thử sẽ quay về chế độ chạy thử.</p>}
      {sw.web_trial_passed && <p className="mt-1 text-[12px] text-emerald-300">Web thử đã chạy xong{sw.web_trial_job ? ` (việc #${sw.web_trial_job})` : ""}.</p>}
      {msg && (
        <p className={clsx("mt-3 flex items-start gap-1.5 text-[12px]", msg.ok ? "text-emerald-300" : "text-rose-300")}>
          {msg.ok ? <CheckCircle2 className="mt-px size-3.5 shrink-0" /> : <AlertCircle className="mt-px size-3.5 shrink-0" />} {msg.text}
        </p>
      )}
    </section>
  );
}
