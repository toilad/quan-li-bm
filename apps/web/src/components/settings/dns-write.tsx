"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Globe, Power, FlaskConical, CheckCircle2, AlertCircle } from "lucide-react";
import { api, errorText } from "@/lib/api";

export type DnsWrite = { enabled: boolean; trial_fqdn: string; trial_passed: boolean; trial_job: number | null; changed_at: string | null; mode: "off" | "trial" | "batch" };

export const DNS_MODE_TEXT: Record<DnsWrite["mode"], string> = {
  off: "TẮT — không ghi DNS thật",
  trial: "Chạy thử — chỉ 1 miền thử",
  batch: "Bật — chạy hàng loạt (vẫn xem trước + xác nhận)",
};

/** Owner-only switch for real DNS writes over the iNET API. OFF until the owner names a trial subdomain and turns it on. */
export function DnsWriteCard() {
  const [sw, setSw] = useState<DnsWrite | null>(null);
  const [trial, setTrial] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const load = useCallback(() => api.get<DnsWrite>("/api/domains/dns-write").then((d) => { setSw(d); setTrial(d.trial_fqdn); }).catch((e) => setMsg({ ok: false, text: errorText(e) })), []);
  useEffect(() => { load(); }, [load]);

  const put = async (body: Partial<{ enabled: boolean; trial_fqdn: string }>, ok: string) => {
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
  return (
    <section className="panel p-5" aria-label="Ghi DNS thật">
      <header className="mb-4 flex items-start gap-3">
        <span className="grid size-10 place-items-center rounded-xl bg-amber-500/15 text-amber-200"><Globe className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[16px] font-semibold">Ghi DNS thật (iNET)</h2>
          <p className="text-[12.5px] text-fg-muted">
            Thêm bản ghi A qua API iNET (PATCH /record, ACTION_ADD — chỉ thêm, không sửa/xoá bản ghi có sẵn). Mặc định TẮT.
            Chạy thử đúng 1 miền anh chỉ định trước; thành công mới được chạy hàng loạt. Mỗi lượt vẫn phải xem trước và xác nhận.
          </p>
        </div>
        <span className={clsx("shrink-0 rounded-full border px-3 py-1 text-[12px] font-semibold",
          sw.mode === "off" ? "border-line text-fg-muted" : sw.mode === "trial" ? "border-amber-400/40 text-amber-300" : "border-emerald-400/40 text-emerald-300")}>
          {DNS_MODE_TEXT[sw.mode]}
        </span>
      </header>
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[260px] flex-1 text-[12px]">
          <span className="mb-1 flex items-center gap-1.5 text-fg-muted"><FlaskConical className="size-3.5" /> Miền thử (miền phụ dưới miền gốc đã tích)</span>
          <input value={trial} onChange={(e) => setTrial(e.target.value)} placeholder="vd: test.mien-goc-da-tich.com"
            aria-label="Miền thử" className="h-9 w-full rounded-lg border border-line bg-ink-850 px-3 font-mono text-[12.5px] outline-none focus:border-brand/60" />
        </label>
        <button onClick={() => put({ trial_fqdn: trial.trim() }, trial.trim() ? `Đã đặt miền thử ${trial.trim()}` : "Đã bỏ miền thử")}
          className="h-9 rounded-lg border border-line px-3 text-[12.5px] text-fg-muted hover:text-fg">Lưu miền thử</button>
        {sw.enabled ? (
          <button onClick={() => put({ enabled: false }, "Đã TẮT ghi DNS thật")}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-rose-400/40 px-3 text-[12.5px] font-semibold text-rose-300 hover:bg-rose-500/10">
            <Power className="size-4" /> Tắt ghi DNS thật
          </button>
        ) : (
          <button onClick={() => put({ enabled: true }, "Đã BẬT ghi DNS thật — chế độ chạy thử")}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 text-[12.5px] font-semibold text-white hover:brightness-110">
            <Power className="size-4" /> Bật ghi DNS thật
          </button>
        )}
      </div>
      {sw.trial_passed && <p className="mt-3 text-[12px] text-emerald-300">Miền thử đã chạy thành công{sw.trial_job ? ` (việc #${sw.trial_job})` : ""}. Đổi miền thử sẽ quay về chế độ chạy thử.</p>}
      {msg && (
        <p className={clsx("mt-3 flex items-start gap-1.5 text-[12px]", msg.ok ? "text-emerald-300" : "text-rose-300")}>
          {msg.ok ? <CheckCircle2 className="mt-px size-3.5 shrink-0" /> : <AlertCircle className="mt-px size-3.5 shrink-0" />} {msg.text}
        </p>
      )}
    </section>
  );
}
