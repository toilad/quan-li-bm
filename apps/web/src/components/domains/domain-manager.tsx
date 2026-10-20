"use client";

import { useState } from "react";
import { Info, Globe2, BadgeX, Boxes, Plug } from "lucide-react";
import { useDomainQueue } from "./use-domain-queue";
import { ScanPanel } from "./scan-panel";
import { RunPanel } from "./run-panel";
import { DomainTable } from "./domain-table";
import { RowDetail } from "./row-detail";
import { NickAccounts } from "./nick-accounts";
import { RootDomains } from "./root-domains";
import { PreviewDialog } from "./preview-dialog";
import { QuickRun } from "./quick-run";
import { BackendStatusBanner, useBackendStatus } from "@/components/shell/backend-status";

export function DomainManager() {
  const { state, dispatch } = useDomainQueue();
  const [preview, setPreview] = useState(false);
  const orphans = state.rows.filter((r) => r.orphan && !r.orphan.resolved);
  const backend = useBackendStatus();

  return (
    <div className="space-y-5">
      <BackendStatusBanner needs={["sheets", "cpanel", "inet"]} status={backend.status} offline={backend.offline} />
      {state.message && (
        <button onClick={() => dispatch({ type: "message", text: null })} className="panel w-full !rounded-2xl px-5 py-3 text-left text-[12.5px] text-sky-100">
          {state.message} <span className="text-fg-subtle">· bấm để ẩn</span>
        </button>
      )}
      {orphans.length > 0 && (
        <button
          onClick={() => dispatch({ type: "select", row: orphans[0].row })}
          className="panel flex w-full items-center gap-3 !rounded-2xl !border-amber-400/30 px-5 py-3 text-left text-[12.5px] text-amber-100"
        >
          <Boxes className="size-4 shrink-0 text-amber-300" />
          <span>
            <b>{orphans.length} tài nguyên đã tạo nhưng chưa gắn vào Sheet</b> (ô B bị xung đột): {orphans.map((r) => r.orphan!.fqdn).join(", ")} — bấm để xem và xử lý.
          </span>
        </button>
      )}
      <QuickRun state={state} dispatch={dispatch} />

      {/* Everything else (scan, row table, accounts, the detailed preview) — folded away; the owner only picks domains */}
      <details className="group space-y-5">
        <summary className="cursor-pointer select-none text-[12.5px] text-fg-subtle hover:text-fg">Chi tiết: quét Sheet, bảng dòng, tài khoản nick, xem trước từng dòng</summary>
        <div className="mt-5 space-y-5">
      <div className="panel flex flex-wrap items-center gap-x-6 gap-y-2 !rounded-2xl px-5 py-3 text-[12.5px]">
        <span className="inline-flex items-center gap-2 font-semibold">
          <Info className="size-4 text-sky-300" /> Tạo miền phụ, không đăng ký domain mới
        </span>
        <span className="inline-flex items-center gap-1.5 text-emerald-200/90">
          <Globe2 className="size-4" /> Có: <span className="font-mono">tencongty.ntp88.com</span> trên các miền gốc đã tích chọn
        </span>
        <span className="inline-flex items-center gap-1.5 text-rose-200/80">
          <BadgeX className="size-4" /> Không: mua / đăng ký <span className="font-mono">tencongty.com</span>
        </span>
        <span className="inline-flex items-center gap-1.5 text-sky-200/90">
          <Plug className="size-4" /> 100% qua API (iNET DNS + cPanel) · không điều khiển trình duyệt
        </span>
      </div>


      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <ScanPanel state={state} dispatch={dispatch} />
        <RunPanel state={state} dispatch={dispatch} onPreview={() => setPreview(true)} />
      </div>

      <RootDomains state={state} dispatch={dispatch} />

      <div className="grid grid-cols-1 gap-5 min-[1500px]:grid-cols-[minmax(0,1fr)_400px]">
        <DomainTable state={state} dispatch={dispatch} />
        <RowDetail state={state} dispatch={dispatch} />
      </div>

      <NickAccounts state={state} dispatch={dispatch} />
        </div>
      </details>

      {preview && <PreviewDialog state={state} dispatch={dispatch} onClose={() => setPreview(false)} />}
    </div>
  );
}
