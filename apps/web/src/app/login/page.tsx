"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { LogIn, UserPlus, ShieldCheck, AlertCircle, Loader2 } from "lucide-react";
import { api, errorText } from "@/lib/api";
import { Logo } from "@/components/shell/sidebar";

type AuthStatus = { authenticated: boolean; user: string | null; setup_needed: boolean; setup_allowed: boolean };

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const next = useSearchParams().get("next") || "/";
  const target = next.startsWith("/") && !next.startsWith("//") ? next : "/"; // never leave the app
  const [st, setSt] = useState<AuthStatus | null>(null);
  const [offline, setOffline] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<AuthStatus>("/api/auth/status")
      .then((s) => (s.authenticated ? window.location.assign(target) : setSt(s)))
      .catch(() => setOffline(true));
  }, [target]);

  const setup = !!st?.setup_needed;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (setup && password !== password2) return setError("Hai lần nhập mật khẩu không khớp");
    setBusy(true);
    try {
      await api.post(setup ? "/api/auth/setup" : "/api/auth/login", { username, password });
      window.location.assign(target);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  };

  const input = "h-11 w-full rounded-xl border border-line bg-ink-850 px-3.5 text-[14px] outline-none focus:border-brand/60";
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="panel w-full max-w-[420px] p-7">
        <div className="mb-6 flex items-center gap-3">
          <Logo />
          <div className="leading-tight">
            <div className="text-[18px] font-bold tracking-tight">Quản Lí <span className="text-gradient">BM</span></div>
            <div className="mt-0.5 text-[12px] text-fg-subtle">{setup ? "Tạo tài khoản chủ (lần đầu)" : "Đăng nhập để tiếp tục"}</div>
          </div>
        </div>

        {offline && <p className="flex items-start gap-1.5 text-[13px] text-rose-300"><AlertCircle className="mt-0.5 size-4 shrink-0" /> Không kết nối được backend — khởi động API rồi tải lại trang.</p>}
        {st && setup && !st.setup_allowed && (
          <p className="text-[13px] text-amber-200">
            Chưa có tài khoản nào. Vì an toàn, tài khoản đầu tiên chỉ tạo được ngay trên máy chạy app, hoặc trên server bằng lệnh
            <code className="mx-1 rounded bg-ink-950/60 px-1.5 py-0.5 font-mono text-[12px]">python -m scripts.create_user &lt;tên&gt;</code>.
          </p>
        )}

        {st && (!setup || st.setup_allowed) && (
          <form onSubmit={submit} className="space-y-3.5">
            <label className="block text-[12.5px]">
              <span className="mb-1 block text-fg-muted">Tên đăng nhập</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required aria-label="Tên đăng nhập" className={input} />
            </label>
            <label className="block text-[12.5px]">
              <span className="mb-1 block text-fg-muted">Mật khẩu{setup ? " (tối thiểu 10 ký tự)" : ""}</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={setup ? "new-password" : "current-password"}
                required aria-label="Mật khẩu" className={input} />
            </label>
            {setup && (
              <label className="block text-[12.5px]">
                <span className="mb-1 block text-fg-muted">Nhập lại mật khẩu</span>
                <input type="password" value={password2} onChange={(e) => setPassword2(e.target.value)} autoComplete="new-password" required aria-label="Nhập lại mật khẩu" className={input} />
              </label>
            )}
            {error && <p className="flex items-start gap-1.5 text-[12.5px] text-rose-300"><AlertCircle className="mt-0.5 size-4 shrink-0" /> {error}</p>}
            <button type="submit" disabled={busy}
              className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand to-brand-2 text-[14px] font-semibold text-white hover:brightness-110 disabled:opacity-50">
              {busy ? <Loader2 className="size-4 animate-spin" /> : setup ? <UserPlus className="size-4" /> : <LogIn className="size-4" />}
              {setup ? "Tạo tài khoản và đăng nhập" : "Đăng nhập"}
            </button>
          </form>
        )}

        <p className="mt-6 flex items-start gap-1.5 text-[11.5px] text-fg-subtle">
          <ShieldCheck className="mt-px size-3.5 shrink-0 text-emerald-300" />
          Phiên đăng nhập lưu trong cookie bảo mật (HttpOnly), hết hạn sau 24 giờ không dùng. Mật khẩu chỉ lưu dạng băm.
        </p>
      </div>
    </div>
  );
}
