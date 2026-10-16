"use client";

import { useState } from "react";
import clsx from "clsx";
import { Users, Plus, PlugZap, PenLine, KeyRound, X, Save, ShieldCheck } from "lucide-react";
import type { Nick } from "@/lib/domain-mock";
import { SimTag, Toggle } from "./ui";
import type { DomainDispatch, DomainState } from "./use-domain-queue";

const STATUS = {
  ok: { text: "Kết nối tốt", cls: "text-emerald-300", dot: "bg-emerald-400" },
  slow: { text: "Phản hồi chậm", cls: "text-amber-300", dot: "bg-amber-300" },
  error: { text: "Lỗi đăng nhập", cls: "text-rose-300", dot: "bg-rose-400" },
  untested: { text: "Chưa kiểm tra", cls: "text-fg-subtle", dot: "bg-fg-subtle" },
} as const;

const maskEmail = (e: string) => e.replace(/^(.{2}).*(@.*)$/, "$1•••$2");
const DOMAIN_RE = /^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})*\.[a-z]{2,}$/;
const IP_RE = /^((25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(25[0-5]|2[0-4]\d|1?\d?\d)$/;

export function NickAccounts({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const [editing, setEditing] = useState<Nick | null>(null);
  const blank: Nick = {
    id: `n${Date.now()}`, name: "", email: "", root: "", ip: "", cpanelHost: "", cpanelUser: "", enabled: true,
    status: "untested", usedToday: 0, dailyLimit: 30, subdomains: 0, lastCheck: "—",
  };

  return (
    <section className="panel p-5">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-sky-500/15 text-sky-200">
            <Users className="size-5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[16px] font-semibold">Tài khoản iNET · miền gốc · IP</h2>
              <SimTag />
            </div>
            <p className="text-[12.5px] text-fg-muted">Mỗi nick sở hữu sẵn 1 miền gốc; miền phụ tạo ra trỏ về IP hosting của nick đó.</p>
          </div>
        </div>
        <button
          onClick={() => setEditing(blank)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.07] px-3 py-1.5 text-[12.5px] font-semibold hover:bg-white/[0.11]"
        >
          <Plus className="size-4" /> Thêm nick
        </button>
      </header>

      {editing && <NickForm nick={editing} onCancel={() => setEditing(null)} onSave={(n) => { dispatch({ type: "saveNick", nick: n }); setEditing(null); }} />}

      <div className="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[920px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
              <th className="py-3 font-medium">Nick</th>
              <th className="py-3 font-medium">Miền gốc (đã sở hữu)</th>
              <th className="py-3 font-medium">IP hosting</th>
              <th className="py-3 font-medium">cPanel</th>
              <th className="py-3 font-medium">Hôm nay</th>
              <th className="py-3 font-medium">Miền phụ</th>
              <th className="py-3 font-medium">Trạng thái</th>
              <th className="py-3 font-medium">Bật</th>
              <th className="w-20 py-3" />
            </tr>
          </thead>
          <tbody>
            {state.nicks.map((n) => {
              const st = STATUS[n.status];
              const pct = Math.round((n.usedToday / n.dailyLimit) * 100);
              return (
                <tr key={n.id} className={clsx("border-b border-line/60", !n.enabled && "opacity-50")}>
                  <td className="py-3 pr-3">
                    <div className="font-semibold">{n.name}</div>
                    <div className="text-[11.5px] text-fg-subtle">{maskEmail(n.email)}</div>
                  </td>
                  <td className="py-3 pr-3 font-mono text-[12.5px]">
                    {n.root}
                    {n.demoRoot && <span className="ml-1.5 rounded bg-white/[0.05] px-1 font-sans text-[10px] text-fg-subtle">demo</span>}
                  </td>
                  <td className="py-3 pr-3 font-mono text-[12.5px] text-fg-muted">{n.ip}</td>
                  <td className="py-3 pr-3 text-[12px] text-fg-muted">
                    <div className="font-mono">{n.cpanelHost}</div>
                    <div className="text-[11px] text-fg-subtle">user {n.cpanelUser} · token •••• (server)</div>
                  </td>
                  <td className="w-36 py-3 pr-3">
                    <div className="flex justify-between text-[11.5px]">
                      <span className={pct >= 90 ? "text-amber-300" : "text-fg-muted"}>{n.usedToday}/{n.dailyLimit}</span>
                      <span className="text-fg-subtle">{pct}%</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className={clsx("h-full rounded-full", pct >= 90 ? "bg-amber-400" : "bg-emerald-400")} style={{ width: `${pct}%` }} />
                    </div>
                  </td>
                  <td className="py-3 pr-3 text-fg-muted">{n.subdomains}</td>
                  <td className="py-3 pr-3">
                    <span className={clsx("inline-flex items-center gap-1.5 text-[12px]", st.cls)}>
                      <span className={clsx("size-1.5 rounded-full", st.dot)} /> {st.text}
                    </span>
                    <div className="text-[11px] text-fg-subtle">{n.lastCheck}</div>
                  </td>
                  <td className="py-3 pr-3">
                    <Toggle on={n.enabled} onChange={() => dispatch({ type: "toggleNick", id: n.id })} label={`Bật/tắt ${n.name}`} />
                  </td>
                  <td className="py-3 pr-1">
                    <div className="flex justify-end gap-1">
                      <IconBtn label="Kiểm tra kết nối (mô phỏng)" onClick={() => dispatch({ type: "testNick", id: n.id })}><PlugZap className="size-4" /></IconBtn>
                      <IconBtn label="Sửa" onClick={() => setEditing(n)}><PenLine className="size-4" /></IconBtn>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 flex items-center gap-1.5 text-[11.5px] text-fg-subtle">
        <ShieldCheck className="size-3.5 text-emerald-300" />
        Mật khẩu / API token iNET và cPanel chỉ lưu phía server (mã hoá), giao diện không bao giờ hiện lại. Miền “demo” là tên giả — chỉ th-ntp.com có trong app cũ.
      </p>
    </section>
  );
}

function IconBtn({ children, label, onClick }: { children: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} title={label} aria-label={label} className="grid size-8 place-items-center rounded-lg text-fg-subtle hover:bg-white/[0.06] hover:text-fg">
      {children}
    </button>
  );
}

function NickForm({ nick, onCancel, onSave }: { nick: Nick; onCancel: () => void; onSave: (n: Nick) => void }) {
  const [n, setN] = useState(nick);
  const set = (k: keyof Nick) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setN({ ...n, [k]: k === "dailyLimit" ? Number(e.target.value) || 0 : e.target.value.trim() });
  const errors = {
    name: !n.name && "Nhập tên nick",
    root: !DOMAIN_RE.test(n.root) && "Miền gốc dạng example.com",
    ip: !IP_RE.test(n.ip) && "IPv4 dạng 203.0.113.10",
    cpanelHost: !n.cpanelHost && "Nhập địa chỉ cPanel",
  };
  const ok = !Object.values(errors).some(Boolean);

  const Field = ({ k, label, mono }: { k: keyof Nick; label: string; mono?: boolean }) => (
    <label className="block text-[12px]">
      <span className="mb-1 block text-fg-muted">{label}</span>
      <input
        value={String(n[k] ?? "")}
        onChange={set(k)}
        className={clsx(
          "h-9 w-full rounded-lg border bg-ink-850 px-3 outline-none focus:border-brand/60",
          mono && "font-mono text-[12.5px]",
          errors[k as keyof typeof errors] ? "border-rose-400/50" : "border-line",
        )}
      />
      {errors[k as keyof typeof errors] && <span className="mt-0.5 block text-[11px] text-rose-300">{errors[k as keyof typeof errors]}</span>}
    </label>
  );

  return (
    <div className="mb-4 rounded-xl border border-brand/30 bg-brand/[0.05] p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[13px] font-semibold">{nick.name ? `Sửa ${nick.name}` : "Thêm nick iNET"}</span>
        <button onClick={onCancel} aria-label="Đóng" className="text-fg-subtle hover:text-fg"><X className="size-4" /></button>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {Field({ k: "name", label: "Tên nick" })}
        {Field({ k: "email", label: "Email đăng nhập iNET" })}
        {Field({ k: "root", label: "Miền gốc đã sở hữu", mono: true })}
        {Field({ k: "ip", label: "IP hosting", mono: true })}
        {Field({ k: "cpanelHost", label: "Địa chỉ cPanel", mono: true })}
        {Field({ k: "cpanelUser", label: "User cPanel", mono: true })}
        {Field({ k: "dailyLimit", label: "Giới hạn miền / ngày" })}
        <label className="block text-[12px]">
          <span className="mb-1 flex items-center gap-1 text-fg-muted"><KeyRound className="size-3.5" /> Mật khẩu / API token</span>
          <input type="password" placeholder="Gửi thẳng lên server, không lưu ở trình duyệt" className="h-9 w-full rounded-lg border border-line bg-ink-850 px-3 outline-none focus:border-brand/60" />
        </label>
      </div>
      <div className="mt-3 flex justify-end gap-2">
        <button onClick={onCancel} className="rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-fg-muted hover:text-fg">Huỷ</button>
        <button
          onClick={() => onSave(n)}
          disabled={!ok}
          className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-1.5 text-[12.5px] font-semibold text-white disabled:opacity-40"
        >
          <Save className="size-3.5" /> Lưu (mô phỏng)
        </button>
      </div>
    </div>
  );
}
