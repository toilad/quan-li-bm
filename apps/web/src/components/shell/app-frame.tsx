"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { Sidebar } from "./sidebar";

type AuthStatus = { authenticated: boolean; user: string | null; setup_needed: boolean; setup_allowed: boolean };

/** App shell. Every screen needs a login; /login is shown on its own. If the backend is offline the screens still
 *  render, and each one says so (nothing can run without the backend anyway). */
export function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname.startsWith("/login");
  const [state, setState] = useState<{ ready: boolean; user: string | null }>({ ready: false, user: null });

  useEffect(() => {
    if (isLogin) return;
    api.get<AuthStatus>("/api/auth/status")
      .then((s) => {
        if (!s.authenticated) window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
        else setState({ ready: true, user: s.user });
      })
      .catch(() => setState({ ready: true, user: null })); // offline: screens show the backend banner
  }, [isLogin, pathname]);

  if (isLogin) return <>{children}</>;
  if (!state.ready) return <div className="grid min-h-screen place-items-center text-[13px] text-fg-subtle">Đang kiểm tra đăng nhập…</div>;
  return (
    <div className="flex min-h-screen">
      <Sidebar user={state.user} />
      <main className="min-w-0 flex-1 px-7 pb-10 pt-6">{children}</main>
    </div>
  );
}
