"use client";

import { useCallback, useEffect, useState } from "react";
import { PlugZap, Settings2, Ban, CheckCircle2 } from "lucide-react";
import { API_URL, ApiError, api, type Status } from "@/lib/api";

export type Need = "sheets" | "drive" | "ai" | "cpanel" | "inet";

/** Backend reachability + what is configured. Polls every 15 s. */
export function useBackendStatus() {
  const [status, setStatus] = useState<Status | null>(null);
  const [offline, setOffline] = useState(false);
  const load = useCallback(async () => {
    try {
      setStatus(await api.get<Status>("/api/status"));
      setOffline(false);
    } catch (e) {
      if (e instanceof ApiError && e.kind === "offline") setOffline(true);
    }
  }, []);
  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, [load]);
  return { status, offline, reload: load };
}

/** Banner at the top of a screen: backend offline, or which services this screen needs are not configured yet. */
export function BackendStatusBanner({ needs, status, offline }: { needs: Need[]; status: Status | null; offline: boolean }) {
  if (offline)
    return (
      <div className="panel flex items-start gap-3 !rounded-2xl !border-rose-400/35 px-5 py-3 text-[12.5px] text-rose-100">
        <PlugZap className="mt-0.5 size-4 shrink-0 text-rose-300" />
        <span>
          <b>Backend chưa chạy</b> ({API_URL}). Không có thao tác nào được thực hiện. Khởi động API + worker rồi tải lại trang.
        </span>
      </div>
    );
  if (!status) return null;
  const missing: string[] = [];
  if (needs.includes("sheets") && !status.google.sheets.configured) missing.push(`Google Sheets (${status.google.sheets.missing.join(", ")})`);
  if (needs.includes("drive") && !status.google.drive.configured) missing.push(`Google Drive (${status.google.drive.missing.join(", ")})`);
  if (needs.includes("ai") && !status.ai.configured) missing.push(`AI (${status.ai.missing.join(", ")})`);
  if (needs.includes("cpanel"))
    status.nicks.filter((n) => !n.cpanel.configured).forEach((n) => missing.push(`cPanel ${n.name} (${n.cpanel.missing.join(", ")})`));
  if (needs.includes("inet")) status.nicks.filter((n) => !n.inet_key).forEach((n) => missing.push(`iNET ${n.name} (INET_API_KEY_${n.id.toUpperCase()})`));
  const unavailable = needs.includes("inet") ? status.unavailable : [];
  if (!missing.length && !unavailable.length)
    return (
      <div className="flex items-center gap-2 px-1 text-[12px] text-emerald-300/90">
        <CheckCircle2 className="size-3.5" /> Đã kết nối backend · các dịch vụ cần cho màn này đã cấu hình
      </div>
    );
  return (
    <div className="panel space-y-1.5 !rounded-2xl !border-amber-400/30 px-5 py-3 text-[12.5px]">
      {missing.length > 0 && (
        <div className="flex items-start gap-2 text-amber-100">
          <Settings2 className="mt-0.5 size-4 shrink-0 text-amber-300" />
          <span><b>Chưa cấu hình:</b> {missing.join(" · ")}. Thao tác cần dịch vụ này sẽ dừng ở trạng thái “Chưa cấu hình”, không báo thành công.</span>
        </div>
      )}
      {unavailable.map((u) => (
        <div key={u.what} className="flex items-start gap-2 text-rose-200/90">
          <Ban className="mt-0.5 size-4 shrink-0 text-rose-300" />
          <span><b>Chưa khả dụng:</b> {u.what} — {u.why}.</span>
        </div>
      ))}
    </div>
  );
}
