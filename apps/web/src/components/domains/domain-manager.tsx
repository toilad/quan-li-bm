"use client";

import { Info, Globe2, BadgeX } from "lucide-react";
import { useDomainQueue } from "./use-domain-queue";
import { ScanPanel } from "./scan-panel";
import { RunPanel } from "./run-panel";
import { DomainTable } from "./domain-table";
import { RowDetail } from "./row-detail";
import { NickAccounts } from "./nick-accounts";

export function DomainManager() {
  const { state, dispatch } = useDomainQueue();

  return (
    <div className="space-y-5">
      <div className="panel flex flex-wrap items-center gap-x-6 gap-y-2 !rounded-2xl px-5 py-3 text-[12.5px]">
        <span className="inline-flex items-center gap-2 font-semibold">
          <Info className="size-4 text-sky-300" /> Chức năng này tạo miền phụ, không đăng ký domain mới
        </span>
        <span className="inline-flex items-center gap-1.5 text-emerald-200/90">
          <Globe2 className="size-4" /> Có: <span className="font-mono">tencongty.th-ntp.com</span> trên miền gốc sẵn có của nick
        </span>
        <span className="inline-flex items-center gap-1.5 text-rose-200/80">
          <BadgeX className="size-4" /> Không: mua / đăng ký <span className="font-mono">tencongty.com</span>
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <ScanPanel state={state} dispatch={dispatch} />
        <RunPanel state={state} dispatch={dispatch} />
      </div>

      <div className="grid grid-cols-1 gap-5 min-[1500px]:grid-cols-[minmax(0,1fr)_400px]">
        <DomainTable state={state} dispatch={dispatch} />
        <RowDetail state={state} dispatch={dispatch} />
      </div>

      <NickAccounts state={state} dispatch={dispatch} />
    </div>
  );
}
