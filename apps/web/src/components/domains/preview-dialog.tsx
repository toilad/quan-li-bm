"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { X, Play, AlertCircle, CheckCircle2, Flag, Undo2, Info, SearchCheck, Loader2 } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { DNS_MODE_TEXT, type DnsWrite } from "@/components/settings/dns-write";
import { labelOf, nickOfRow, previewIssue, runItems, usablePool, type DomainDispatch, type DomainState } from "./use-domain-queue";
import { RootSelect } from "./root-select";

type ServerRow = {
  row: number; fqdn?: string; root?: string; nick?: string; ip?: string; hosting_ip?: string; dns_provider?: string; nameservers?: string[];
  domain_id?: number; existing?: { id: number; type: string; data: string }[]; public_dns?: string[]; action: "add" | "exists" | "refuse";
  reason?: string; checks?: string[];
};
type ServerPreview = {
  mode: DnsWrite["mode"]; trial_fqdn: string; blocked: string | null; token: string | null; rows: ServerRow[];
  api_log: { fqdn: string; level: string; message: string }[];
};

/** Final check before a run: every domain is visible and editable; blocked rows are skipped, never renamed. */
export function PreviewDialog({ state, dispatch, onClose }: { state: DomainState; dispatch: DomainDispatch; onClose: () => void }) {
  const rows = state.rows.filter((r) => r.checked && r.status === "idle");
  const ok = rows.filter((r) => !previewIssue(r, state));
  const willRun = ok.slice(0, state.batchLimit);
  const overLimit = ok.length - willRun.length;
  const noRoots = !usablePool(state).length;
  const usedRoots = new Set(willRun.map((r) => r.root));
  // Read-only API check of exactly what will run; the confirm button only works for the latest check.
  const items = runItems(state);
  const key = JSON.stringify(items);
  const [check, setCheck] = useState<{ key: string; res: ServerPreview } | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const fresh = check && check.key === key ? check.res : null;
  const server = new Map((fresh?.rows ?? []).map((r) => [r.row, r]));
  const runServerCheck = async () => {
    setChecking(true);
    setCheckError(null);
    try {
      setCheck({ key, res: await api.post<ServerPreview>("/api/domains/preview", { items }) });
    } catch (e) {
      setCheckError(errorText(e));
    } finally {
      setChecking(false);
    }
  };

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
          {fresh && (
            <Pill cls={fresh.mode === "off" ? "text-rose-300" : fresh.mode === "trial" ? "text-amber-300" : "text-emerald-300"}>
              Ghi thật: {DNS_MODE_TEXT[fresh.mode]}{fresh.mode === "trial" && fresh.trial_fqdn ? ` (${fresh.trial_fqdn})` : ""}
            </Pill>
          )}
        </div>
        {fresh?.blocked && (
          <p className="mx-6 mt-3 flex items-start gap-1.5 rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-[12.5px] text-rose-200">
            <AlertCircle className="mt-0.5 size-4 shrink-0" /> {fresh.blocked}
          </p>
        )}
        {checkError && <p className="mx-6 mt-3 text-[12.5px] text-rose-300">{checkError}</p>}
        {check && !fresh && <p className="mx-6 mt-3 text-[12.5px] text-amber-300">Đã đổi miền gốc / tên sau lần kiểm tra — kiểm tra lại qua API trước khi chạy.</p>}

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
                    <td className="max-w-[330px] py-2.5">
                      {issue ? (
                        <span className="flex items-start gap-1 text-[12px] text-rose-300"><AlertCircle className="mt-0.5 size-3.5 shrink-0" /> {issue}</span>
                      ) : server.get(r.row) ? (
                        <ServerCell s={server.get(r.row)!} />
                      ) : (
                        <span className="flex items-center gap-1 text-[12px] text-fg-muted"><Info className="size-3.5" /> Chưa kiểm tra qua API</span>
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
            <Info className="size-3.5" /> Chạy qua API iNET + cPanel trên server. Đóng trình duyệt vẫn tiếp tục.
            {fresh && fresh.api_log.length > 0 && (
              <details className="ml-2">
                <summary className="cursor-pointer text-fg-muted">{fresh.api_log.length} lời gọi API (chỉ đọc)</summary>
                <ul className="mt-1 max-h-40 overflow-auto font-mono text-[11px]">{fresh.api_log.map((l, i) => <li key={i}>{l.message}</li>)}</ul>
              </details>
            )}
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-xl border border-line px-4 py-2 text-[13px] text-fg-muted hover:text-fg">Quay lại</button>
            <button
              onClick={runServerCheck}
              disabled={!willRun.length || noRoots || checking}
              className="inline-flex items-center gap-1.5 rounded-xl border border-line px-4 py-2 text-[13px] font-semibold text-fg hover:bg-white/[0.05] disabled:opacity-40"
            >
              {checking ? <Loader2 className="size-4 animate-spin" /> : <SearchCheck className="size-4" />} Kiểm tra qua API (chỉ đọc)
            </button>
            <button
              onClick={() => {
                if (fresh?.token) dispatch({ type: "start", token: fresh.token });
                onClose();
              }}
              disabled={!willRun.length || noRoots || !fresh?.token}
              title={fresh?.token ? undefined : "Kiểm tra qua API trước — chỉ chạy đúng kết quả đã kiểm tra"}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-brand to-brand-2 px-4 py-2 text-[13px] font-semibold text-white hover:brightness-110 disabled:opacity-40"
            >
              <Play className="size-4" /> Xác nhận chạy {fresh?.token ? fresh.rows.filter((x) => x.action !== "refuse").length : willRun.length} dòng
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

/** What the read-only API check found for one row: subdomain, nick, IP, DNS provider, existing records. */
function ServerCell({ s }: { s: ServerRow }) {
  const tone = s.action === "refuse" ? "text-rose-300" : s.action === "exists" ? "text-sky-300" : "text-emerald-300";
  return (
    <div className="space-y-0.5 text-[11.5px]">
      <div className={clsx("flex items-start gap-1 text-[12px] font-medium", tone)}>
        {s.action === "refuse" ? <AlertCircle className="mt-0.5 size-3.5 shrink-0" /> : <CheckCircle2 className="mt-0.5 size-3.5 shrink-0" />}
        {s.action === "add" ? `Sẽ thêm ${s.fqdn} A ${s.ip}` : s.action === "exists" ? `Đã có ${s.fqdn} A ${s.ip} — không gửi lại` : s.reason}
      </div>
      {s.nick && (
        <div className="text-fg-subtle">
          {s.nick} · IP hosting {s.hosting_ip || "cPanel không báo"} · DNS: {s.dns_provider ?? "—"}{s.domain_id ? ` · iNET ID ${s.domain_id}` : ""}
        </div>
      )}
      {s.nameservers && <div className="font-mono text-[10.5px] text-fg-subtle">NS {s.nameservers.join(", ")}</div>}
      {s.existing && s.existing.length > 0 && <div className="text-fg-subtle">Bản ghi cùng tên: {s.existing.map((e) => `${e.type} ${e.data}`).join(", ")}</div>}
      {s.public_dns && <div className="text-fg-subtle">DNS công khai: {s.public_dns.length ? s.public_dns.join(", ") : "chưa có"}</div>}
    </div>
  );
}

function Pill({ children, cls }: { children: React.ReactNode; cls: string }) {
  return <span className={clsx("rounded-full border border-line bg-ink-850/70 px-3 py-1 font-medium", cls)}>{children}</span>;
}
