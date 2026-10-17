"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { KeyRound, Save, Trash2, ShieldCheck, FileSpreadsheet, Bot, Server, Users, Link2, PlugZap, CheckCircle2, AlertCircle, Copy, Image as ImageIcon } from "lucide-react";
import { API_URL, api, errorText } from "@/lib/api";
import { DnsWriteCard } from "./dns-write";

type Field = { name: string; group: string; label: string; secret: boolean; set: boolean; source: "app" | "env" | "none"; updated_at: string | null; server_only: boolean; value?: string; default?: string };
type Settings = { fields: Field[]; google: { mode: string | null; client_type: string | null; redirect_uri: string; connected: boolean } };
type Msg = { tone: "ok" | "err" | "info"; text: string } | null;

const GROUPS: { key: string; title: string; icon: typeof Bot; note: string }[] = [
  { key: "google", title: "Google Sheets & Drive", icon: FileSpreadsheet, note: "OAuth của chính anh: quyền Sheets + chỉ các file do app tạo trên Drive." },
  { key: "ai", title: "AI (Anthropic)", icon: Bot, note: "Dùng để đọc phôi scan và viết nội dung website." },
  { key: "photos", title: "Ảnh cho website (Pexels / Pixabay)", icon: ImageIcon, note: "Có khoá Pexels thì dùng Pexels, không thì Pixabay. Khoá Pexels: pexels.com/api/key · khoá Pixabay: pixabay.com/api/docs (mục Parameters). Ảnh tải về và upload kèm web; chân trang ghi nguồn + tên tác giả. Chưa có khoá → web dùng khung màu." },
  { key: "server", title: "Máy chủ", icon: Server, note: "Địa chỉ công khai khi đưa app lên server (dùng cho OAuth redirect)." },
  { key: "nick:n1", title: "Nick iNET-1", icon: Users, note: "Khoá iNET + user/token cPanel của hosting nick này." },
  { key: "nick:n2", title: "Nick iNET-2", icon: Users, note: "Khoá iNET + user/token cPanel của hosting nick này." },
  { key: "nick:n3", title: "Nick iNET-3", icon: Users, note: "Khoá iNET + user/token cPanel của hosting nick này." },
];

export function ApiSettings() {
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<Record<string, Msg>>({});

  const load = useCallback(() => api.get<Settings>("/api/settings").then((d) => { setData(d); setError(null); }).catch((e) => setError(errorText(e))), []);
  useEffect(() => {
    load();
    const q = new URLSearchParams(window.location.search).get("google");
    if (q === "connected") setMsg((m) => ({ ...m, google: { tone: "ok", text: "Đã kết nối Google — quyền truy cập lưu mã hoá phía server." } }));
    if (q === "error") {
      const reason = new URLSearchParams(window.location.search).get("reason") ?? "";
      const text = reason.startsWith("missing_scope:")
        ? `Google chưa được cấp đủ quyền (thiếu ${reason.slice(14).replace("+", " và ")}). Bấm Kết nối lại và tick đủ các ô quyền.`
        : `Kết nối Google không thành công (${reason}).`;
      setMsg((m) => ({ ...m, google: { tone: "err", text } }));
    }
  }, [load]);

  const say = (group: string, m: Msg) => setMsg((x) => ({ ...x, [group]: m }));
  const save = async (f: Field, value: string) => {
    try {
      await api.put(f, value);
      say(f.group, { tone: "ok", text: value ? `Đã lưu ${f.label}${f.secret ? " (mã hoá)" : ""}` : `Đã xoá ${f.label} khỏi app` });
      load();
    } catch (e) {
      say(f.group, { tone: "err", text: errorText(e) });
    }
  };
  const run = async (group: string, label: string, fn: () => Promise<unknown>, show: (r: never) => string) => {
    say(group, { tone: "info", text: `${label}…` });
    try {
      say(group, { tone: "ok", text: show((await fn()) as never) });
    } catch (e) {
      say(group, { tone: "err", text: errorText(e) });
    }
  };

  if (error) return <section className="panel p-6 text-[13px] text-rose-200">{error}</section>;
  if (!data) return <section className="panel p-6 text-[13px] text-fg-subtle">Đang tải…</section>;

  return (
    <div className="space-y-5">
      <div className="panel flex flex-wrap items-center gap-x-6 gap-y-2 !rounded-2xl px-5 py-3 text-[12.5px]">
        <span className="inline-flex items-center gap-2 font-semibold"><ShieldCheck className="size-4 text-emerald-300" /> Bí mật lưu mã hoá phía server</span>
        <span className="text-fg-muted">Ô bí mật chỉ để ghi — không bao giờ hiển thị lại, không ghi vào log. Giá trị đặt ở đây được ưu tiên hơn file .env.</span>
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {GROUPS.map((g) => {
          const fields = data.fields.filter((f) => f.group === g.key && !f.server_only);
          const m = msg[g.key];
          return (
            <section key={g.key} className="panel p-5">
              <header className="mb-4 flex items-start gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-sky-500/15 text-sky-200"><g.icon className="size-5" /></span>
                <div>
                  <h2 className="text-[16px] font-semibold">{g.title}</h2>
                  <p className="text-[12.5px] text-fg-muted">{g.note}</p>
                </div>
              </header>
              {g.key === "google" && <GoogleConnect google={data.google} />}
              <div className="space-y-3">
                {fields.map((f) => <FieldRow key={f.name} f={f} onSave={(v) => save(f, v)} />)}
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {g.key === "google" && (
                  <Btn onClick={() => run("google", "Đang kiểm tra Google (chỉ đọc)", () => api.get("/api/google/check"),
                    (r: { sheet: { title: string; tabs: string[]; tab_found: boolean; tab: string; header_rows?: string[][]; data_starts_at_row?: number };
                          drive: { account: string; folder_ok: boolean | null; folder_problem?: string } }) =>
                      `Sheet “${r.sheet.title}” · tab ${r.sheet.tab}: ${r.sheet.tab_found ? "có" : "KHÔNG có"} (${r.sheet.tabs.join(", ")})` +
                      (r.sheet.header_rows ? ` · dòng 1–2: ${r.sheet.header_rows.map((x) => x.slice(0, 3).join(" | ")).join(" / ")} → app đọc dữ liệu từ dòng ${r.sheet.data_starts_at_row}` : "") +
                      ` · Drive: ${r.drive.account}` + (r.drive.folder_problem ? ` · ⚠ ${r.drive.folder_problem}` : ""))}>
                    <PlugZap className="size-4" /> Kiểm tra (chỉ đọc)
                  </Btn>
                )}
                {g.key === "ai" && (
                  <Btn onClick={() => run("ai", "Đang hỏi Models API", () => api.get("/api/ai/check"),
                    (r: { id: string; display_name: string; max_input_tokens: number; sdk: string }) => `Model ${r.id} (${r.display_name}) có với khoá này · ngữ cảnh ${r.max_input_tokens?.toLocaleString?.() ?? "?"} token · SDK ${r.sdk}`)}>
                    <PlugZap className="size-4" /> Kiểm tra model
                  </Btn>
                )}
                {g.key === "photos" && (
                  <>
                    {(["pexels", "pixabay"] as const).map((p) => (
                      <Btn key={p} onClick={() => run("photos", `Đang thử 1 lượt tìm ảnh ${p === "pexels" ? "Pexels" : "Pixabay"}`, () => api.get(`/api/photos/check?provider=${p}`),
                        (r: { found: number; remaining: string | null; in_use: boolean }) =>
                          `Khoá ${p === "pexels" ? "Pexels" : "Pixabay"} dùng được · còn ${r.remaining ?? "?"} lượt${r.in_use ? " · đang dùng cho web" : ""}`)}>
                        <PlugZap className="size-4" /> Kiểm tra {p === "pexels" ? "Pexels" : "Pixabay"}
                      </Btn>
                    ))}
                  </>
                )}
                {g.key.startsWith("nick:") && (
                  <Btn onClick={() => run(g.key, "Đang đọc cPanel + iNET (chỉ đọc)", () => api.post(`/api/domains/check/${g.key.slice(5)}`),
                    (r: { cpanel: { ok: boolean; error?: string; on_hosting?: string[]; missing?: string[]; version?: string }; inet: { ok: boolean; error?: string; note?: string } }) =>
                      `cPanel: ${r.cpanel.ok ? `${r.cpanel.version ? `bản ${r.cpanel.version}, ` : ""}${r.cpanel.on_hosting?.length} miền gốc có trên hosting, ${r.cpanel.missing?.length} chưa có` : r.cpanel.error} · iNET: ${r.inet.ok ? r.inet.note : r.inet.error}`)}>
                    <PlugZap className="size-4" /> Kiểm tra hosting (chỉ đọc)
                  </Btn>
                )}
              </div>
              {m && (
                <p className={clsx("mt-3 flex items-start gap-1.5 text-[12px]", m.tone === "ok" ? "text-emerald-300" : m.tone === "err" ? "text-rose-300" : "text-fg-muted")}>
                  {m.tone === "ok" ? <CheckCircle2 className="mt-px size-3.5 shrink-0" /> : <AlertCircle className="mt-px size-3.5 shrink-0" />} {m.text}
                </p>
              )}
            </section>
          );
        })}
      </div>
      <DnsWriteCard />
    </div>
  );
}

function GoogleConnect({ google }: { google: Settings["google"] }) {
  return (
    <div className="mb-4 rounded-xl border border-line bg-ink-850/50 p-3.5 text-[12px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={clsx("inline-flex items-center gap-1.5 font-semibold", google.connected ? "text-emerald-300" : "text-amber-300")}>
          <Link2 className="size-4" /> {google.connected ? "Đã kết nối Google" : "Chưa kết nối Google"}
          {google.mode && <span className="font-normal text-fg-subtle">· {google.mode === "oauth" ? "OAuth" : "service account"}</span>}
        </span>
        <a href={`${API_URL}/api/google/oauth/start`} className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-1.5 text-[12.5px] font-semibold text-white hover:brightness-110">
          {google.connected ? "Kết nối lại" : "Kết nối Google"}
        </a>
      </div>
      <p className="mt-2 text-fg-subtle">
        Trong Google Cloud: tạo OAuth client loại <b className="text-fg-muted">Web application</b>, bật Google Sheets API + Google Drive API, thêm Redirect URI:
      </p>
      <div className="mt-1 flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-ink-950/60 px-2 py-1 font-mono text-[11.5px] text-fg-muted">{google.redirect_uri}</code>
        <button onClick={() => navigator.clipboard?.writeText(google.redirect_uri)} aria-label="Chép Redirect URI" className="text-fg-subtle hover:text-fg"><Copy className="size-3.5" /></button>
      </div>
      <p className="mt-1 text-fg-subtle">Khi chạy trên server, đặt “Địa chỉ API công khai” ở mục Máy chủ để Redirect URI dùng tên miền của server.</p>
    </div>
  );
}

function FieldRow({ f, onSave }: { f: Field; onSave: (value: string) => void }) {
  const [v, setV] = useState(f.secret ? "" : f.value ?? "");
  const isJson = f.name === "GOOGLE_OAUTH_CLIENT_JSON";
  useEffect(() => { if (!f.secret) setV(f.value ?? ""); }, [f.value, f.secret]);
  return (
    <label className="block text-[12px]">
      <span className="mb-1 flex flex-wrap items-center gap-2 text-fg-muted">
        {f.secret && <KeyRound className="size-3.5" />} {f.label}
        <span className={clsx("rounded px-1.5 py-0.5 text-[10.5px] font-semibold", f.set ? "bg-emerald-400/10 text-emerald-300" : "bg-white/[0.05] text-fg-subtle")}>
          {f.set ? (f.source === "app" ? "đã đặt trong app" : "đặt trong .env") : "chưa đặt"}
        </span>
      </span>
      <div className="flex gap-2">
        {isJson ? (
          <textarea value={v} onChange={(e) => setV(e.target.value)} rows={2} placeholder={f.set ? "Đã có — dán file JSON mới để thay" : "Dán nội dung file JSON tải từ Google Cloud"}
            className="min-w-0 flex-1 rounded-lg border border-line bg-ink-850 px-3 py-2 font-mono text-[11.5px] outline-none focus:border-brand/60" aria-label={f.label} />
        ) : (
          <input type={f.secret ? "password" : "text"} value={v} onChange={(e) => setV(e.target.value)} autoComplete="off"
            placeholder={f.secret ? (f.set ? "Đã có — nhập để thay" : "Nhập để lưu (không hiện lại)") : f.default ? `mặc định: ${f.default}` : ""}
            className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-ink-850 px-3 font-mono text-[12.5px] outline-none focus:border-brand/60" aria-label={f.label} />
        )}
        <button onClick={(e) => { e.preventDefault(); onSave(v); if (f.secret) setV(""); }} disabled={!v.trim() || (!f.secret && v === (f.value ?? ""))}
          className="inline-flex items-center gap-1 rounded-lg bg-white/[0.07] px-3 text-[12px] font-semibold hover:bg-white/[0.11] disabled:opacity-40" aria-label={`Lưu ${f.label}`}>
          <Save className="size-3.5" /> Lưu
        </button>
        {f.source === "app" && (
          <button onClick={(e) => { e.preventDefault(); onSave(""); }} title="Xoá khỏi app (quay về .env nếu có)" aria-label={`Xoá ${f.label}`}
            className="grid w-9 place-items-center rounded-lg border border-line text-fg-subtle hover:text-rose-300"><Trash2 className="size-3.5" /></button>
        )}
      </div>
    </label>
  );
}

function Btn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-[12.5px] font-medium text-fg-muted hover:border-line-strong hover:text-fg">
      {children}
    </button>
  );
}
