"use client";

import { useState } from "react";
import clsx from "clsx";
import { Users, Plus, PlugZap, PenLine, KeyRound, X, Save, ShieldCheck, Check, Ban, HelpCircle } from "lucide-react";
import { API_LABEL, quotaFull, type ApiCap, type Nick } from "@/lib/domain-mock";
import { SimTag, Toggle } from "./ui";
import type { DomainDispatch, DomainState } from "./use-domain-queue";

const STATUS = {
  ok: { text: "Kết nối tốt", cls: "text-emerald-300", dot: "bg-emerald-400" },
  slow: { text: "Phản hồi chậm", cls: "text-amber-300", dot: "bg-amber-300" },
  error: { text: "Lỗi xác thực API", cls: "text-rose-300", dot: "bg-rose-400" },
  untested: { text: "Chưa kiểm tra", cls: "text-fg-subtle", dot: "bg-fg-subtle" },
} as const;

const maskEmail = (e: string) => (e ? e.replace(/^(.{2}).*(@.*)$/, "$1•••$2") : "—");
const IP_RE = /^((25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(25[0-5]|2[0-4]\d|1?\d?\d)$/;

export function NickAccounts({ state, dispatch }: { state: DomainState; dispatch: DomainDispatch }) {
  const [editing, setEditing] = useState<Nick | null>(null);
  const blank: Nick = {
    id: `n${Date.now()}`, name: "", email: "", roots: [], ip: "", cpanelHost: "", cpanelUser: "", enabled: true,
    status: "untested", usedToday: 0, dailyLimit: null, weight: 1, subdomains: 0, lastCheck: "—",
    api: { dns: { state: "untested" }, cpanel: { state: "untested" } },
  };
  const totalWeight = state.nicks.filter((n) => n.enabled).reduce((s, n) => s + n.weight, 0) || 1;

  return (
    <section className="panel p-5">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-sky-500/15 text-sky-200">
            <Users className="size-5" />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[16px] font-semibold">Tài khoản iNET & hosting</h2>
              <SimTag />
            </div>
            <p className="text-[12.5px] text-fg-muted">Mỗi nick: miền gốc đã sở hữu, IP hosting, cPanel và thông tin API riêng. Mọi bước chạy qua API.</p>
          </div>
        </div>
        <button
          disabled
          title="Chưa khả dụng: thêm nick bằng file cấu hình server (config/nicks.json + .env)"
          onClick={() => setEditing(blank)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.07] px-3 py-1.5 text-[12.5px] font-semibold hover:bg-white/[0.11]"
        >
          <Plus className="size-4" /> Thêm nick
        </button>
      </header>

      {editing && (
        <NickForm
          nick={editing}
          onCancel={() => setEditing(null)}
          onSave={(n) => {
            dispatch({ type: "saveNick", nick: n });
            setEditing(null);
          }}
        />
      )}

      <div className="scroll-thin overflow-x-auto">
        <table className="w-full min-w-[1040px] text-left text-[13px]">
          <thead>
            <tr className="border-b border-line text-[11.5px] uppercase tracking-wide text-fg-subtle">
              <th className="py-3 font-medium">Nick</th>
              <th className="py-3 font-medium">Miền · IP hosting</th>
              <th className="py-3 font-medium">cPanel</th>
              <th className="py-3 font-medium">Quyền API</th>
              <th className="py-3 font-medium">Hôm nay / hạn mức</th>
              <th className="py-3 font-medium">Tỷ trọng</th>
              <th className="py-3 font-medium">Trạng thái</th>
              <th className="py-3 font-medium">Bật</th>
              <th className="w-20 py-3" />
            </tr>
          </thead>
          <tbody>
            {state.nicks.map((n) => {
              const st = STATUS[n.status];
              const pct = n.dailyLimit ? Math.min(100, Math.round((n.usedToday / n.dailyLimit) * 100)) : 0;
              return (
                <tr key={n.id} className={clsx("border-b border-line/60 align-top", !n.enabled && "opacity-50")}>
                  <td className="py-3 pr-3">
                    <div className="font-semibold">{n.name}</div>
                    <div className="text-[11.5px] text-fg-subtle">{maskEmail(n.email)}</div>
                  </td>
                  <td className="py-3 pr-3">
                    <div className="text-[12.5px]">{n.roots.filter((r) => state.selectedRoots.includes(r.name)).length}/{n.roots.length} miền đã chọn</div>
                    <div className="mt-0.5 font-mono text-[11.5px] text-fg-muted">{n.ip}</div>
                  </td>
                  <td className="py-3 pr-3 text-[12px] text-fg-muted">
                    {n.hosting && <div className="text-[11px] text-fg-subtle">Hosting <span className="font-mono text-fg-muted">{n.hosting}</span></div>}
                    <div className="font-mono">{n.cpanelHost}</div>
                    <div className="text-[11px] text-fg-subtle">{n.cpanelUser ? `user ${n.cpanelUser}` : "user: nhập ở server"} · token •••• (server)</div>
                  </td>
                  <td className="py-3 pr-3">
                    <div className="space-y-1">
                      <Cap label={API_LABEL.dns} cap={n.api.dns} />
                      <Cap label={API_LABEL.cpanel} cap={n.api.cpanel} />
                    </div>
                  </td>
                  <td className="w-40 py-3 pr-3">
                    {n.dailyLimit === null ? (
                      <>
                        <div className="text-[11.5px] text-fg-muted">{n.usedToday} miền hôm nay</div>
                        <div className="mt-0.5 text-[11px] text-amber-300/90">Chưa đặt hạn mức</div>
                      </>
                    ) : (
                      <>
                        <div className="flex justify-between text-[11.5px]">
                          <span className={quotaFull(n) ? "text-rose-300" : pct >= 80 ? "text-amber-300" : "text-fg-muted"}>{n.usedToday}/{n.dailyLimit}</span>
                          <span className="text-fg-subtle">{quotaFull(n) ? "đã đủ" : `${pct}%`}</span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                          <div className={clsx("h-full rounded-full", quotaFull(n) ? "bg-rose-400" : pct >= 80 ? "bg-amber-400" : "bg-emerald-400")} style={{ width: `${pct}%` }} />
                        </div>
                      </>
                    )}
                  </td>
                  <td className="py-3 pr-3 text-[12px] text-fg-muted">
                    {n.weight} <span className="text-fg-subtle">({Math.round((n.weight / totalWeight) * 100)}%)</span>
                  </td>
                  <td className="py-3 pr-3">
                    <span className={clsx("inline-flex items-center gap-1.5 text-[12px]", st.cls)}>
                      <span className={clsx("size-1.5 rounded-full", st.dot)} /> {st.text}
                    </span>
                    <div className="text-[11px] text-fg-subtle">{n.lastCheck}</div>
                  </td>
                  <td className="py-3 pr-3">
                    <span title="Bật/tắt nick: cấu hình ở server"><Toggle on={n.enabled} onChange={() => dispatch({ type: "toggleNick", id: n.id })} label={`Bật/tắt ${n.name}`} /></span>
                  </td>
                  <td className="py-3 pr-1">
                    <div className="flex justify-end gap-1">
                      <IconBtn label="Kiểm tra API: chưa khả dụng" onClick={() => dispatch({ type: "testNick", id: n.id })}><PlugZap className="size-4" /></IconBtn>
                      <IconBtn label="Sửa" onClick={() => setEditing(n)}><PenLine className="size-4" /></IconBtn>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3 space-y-1 text-[11.5px] text-fg-subtle">
        <p className="flex items-center gap-1.5">
          <ShieldCheck className="size-3.5 text-emerald-300" />
          API key / token chỉ lưu phía server (mã hoá), giao diện không hiện lại. Không dùng điều khiển trình duyệt — nick thiếu quyền API sẽ bị chặn và báo rõ.
        </p>
        <p>Hạn mức/ngày để trống khi chưa có căn cứ (không mặc định). API iNET giới hạn chung 60 yêu cầu/phút · 1.000/giờ · 10.000/ngày cho mỗi khoá (tài liệu chính thức) — hàng đợi sẽ tự giãn nhịp.</p>
        <p>3 nick đọc từ portal iNET ngày 16/10/2026 (chỉ đọc, không thay đổi gì trên tài khoản). Chọn miền gốc ở bảng “Miền gốc dùng để tạo miền phụ”. User cPanel không lưu trong mã nguồn.</p>
      </div>
    </section>
  );
}

function Cap({ label, cap }: { label: string; cap: ApiCap }) {
  const m = {
    ok: { icon: Check, cls: "text-emerald-300", text: "có quyền" },
    blocked: { icon: Ban, cls: "text-rose-300", text: "bị chặn" },
    untested: { icon: HelpCircle, cls: "text-fg-subtle", text: "chưa kiểm tra" },
  }[cap.state];
  return (
    <div className={clsx("flex items-start gap-1 text-[11.5px]", m.cls)} title={cap.note}>
      <m.icon className="mt-px size-3.5 shrink-0" />
      <span>
        {label}: {m.text}
        {cap.note && <span className="block text-[10.5px] opacity-80">{cap.note}</span>}
      </span>
    </div>
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
  const [limit, setLimit] = useState(nick.dailyLimit === null ? "" : String(nick.dailyLimit));
  const set = (k: "name" | "email" | "ip" | "cpanelHost" | "cpanelUser") => (e: React.ChangeEvent<HTMLInputElement>) =>
    setN({ ...n, [k]: e.target.value.trim() });
  const errors: Record<string, string | false> = {
    name: !n.name && "Nhập tên nick",
    ip: !IP_RE.test(n.ip) && "IPv4 dạng 203.0.113.10",
    cpanelHost: !n.cpanelHost && "Nhập địa chỉ cPanel",
    limit: limit !== "" && !(Number(limit) > 0) && "Số dương hoặc để trống",
    weight: !(n.weight > 0) && "Tỷ trọng > 0",
  };
  const ok = !Object.values(errors).some(Boolean);

  const field = (k: "name" | "email" | "ip" | "cpanelHost" | "cpanelUser", label: string, mono?: boolean) => (
    <label className="block text-[12px]">
      <span className="mb-1 block text-fg-muted">{label}</span>
      <input
        value={n[k]}
        onChange={set(k)}
        className={clsx("h-9 w-full rounded-lg border bg-ink-850 px-3 outline-none focus:border-brand/60", mono && "font-mono text-[12.5px]", errors[k] ? "border-rose-400/50" : "border-line")}
      />
      {errors[k] && <span className="mt-0.5 block text-[11px] text-rose-300">{errors[k]}</span>}
    </label>
  );
  const secret = (label: string) => (
    <label className="block text-[12px]">
      <span className="mb-1 flex items-center gap-1 text-fg-muted"><KeyRound className="size-3.5" /> {label}</span>
      <input type="password" placeholder="Gửi thẳng lên server, không lưu ở trình duyệt" className="h-9 w-full rounded-lg border border-line bg-ink-850 px-3 outline-none focus:border-brand/60" />
    </label>
  );

  return (
    <div className="mb-4 rounded-xl border border-brand/30 bg-brand/[0.05] p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[13px] font-semibold">{nick.name ? `Sửa ${nick.name}` : "Thêm nick iNET / hosting"}</span>
        <button onClick={onCancel} aria-label="Đóng" className="text-fg-subtle hover:text-fg"><X className="size-4" /></button>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {field("name", "Tên nick")}
        {field("email", "Email tài khoản iNET")}
        {field("ip", "IP hosting", true)}
        {field("cpanelHost", "Địa chỉ cPanel", true)}
        {field("cpanelUser", "User cPanel", true)}
        {secret("Khoá API iNET (developers.inet.vn)")}
        {secret("API token cPanel")}
        <label className="block text-[12px]">
          <span className="mb-1 block text-fg-muted">Hạn mức miền / ngày</span>
          <input
            value={limit}
            onChange={(e) => setLimit(e.target.value.trim())}
            placeholder="Để trống nếu chưa rõ"
            className={clsx("h-9 w-full rounded-lg border bg-ink-850 px-3 outline-none focus:border-brand/60", errors.limit ? "border-rose-400/50" : "border-line")}
          />
          {errors.limit && <span className="mt-0.5 block text-[11px] text-rose-300">{errors.limit}</span>}
        </label>
        <label className="block text-[12px]">
          <span className="mb-1 block text-fg-muted">Tỷ trọng phân bổ</span>
          <input
            type="number"
            min={1}
            value={n.weight}
            onChange={(e) => setN({ ...n, weight: Number(e.target.value) || 0 })}
            className={clsx("h-9 w-full rounded-lg border bg-ink-850 px-3 outline-none focus:border-brand/60", errors.weight ? "border-rose-400/50" : "border-line")}
          />
        </label>
      </div>
      <p className="mt-2 text-[11px] text-fg-subtle">Danh sách tên miền của nick được đọc qua API iNET sau khi lưu khoá — không nhập tay. Loại khoá API cụ thể sẽ chốt theo tài liệu chính thức trước khi làm backend.</p>
      <div className="mt-3 flex justify-end gap-2">
        <button onClick={onCancel} className="rounded-lg border border-line px-3 py-1.5 text-[12.5px] text-fg-muted hover:text-fg">Huỷ</button>
        <button
          onClick={() => onSave({ ...n, dailyLimit: limit === "" ? null : Number(limit) })}
          disabled={!ok}
          className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand to-brand-2 px-3 py-1.5 text-[12.5px] font-semibold text-white disabled:opacity-40"
        >
          <Save className="size-3.5" /> Lưu (mô phỏng)
        </button>
      </div>
    </div>
  );
}
