"use client";

import { useState } from "react";
import { Info, ShieldCheck, FileX2, Plug, Boxes, Sheet, Filter } from "lucide-react";
import { SimTag } from "@/components/domains/ui";
import { scanForWeb } from "@/lib/web-mock";
import { useWebQueue } from "./use-web-queue";
import { WebRunPanel } from "./web-run-panel";
import { WebTable } from "./web-table";
import { WebDetail } from "./web-detail";
import { TemplateGallery } from "./template-gallery";
import { WebConfirmDialog } from "./web-confirm-dialog";

export function WebBuilder() {
  const { state, dispatch } = useWebQueue();
  const [confirm, setConfirm] = useState(false);
  const scan = scanForWeb();
  const live = state.rows.filter((r) => r.liveNotWritten && !r.liveNotWritten.resolved);
  const noHost = state.rows.filter((r) => !r.host).length;
  const autoCount = state.rows.filter((r) => r.templateSource === "auto").length;
  const fallback = state.rows.filter((r) => !r.detection.keyword).length;

  return (
    <div className="space-y-5">
      <div className="panel flex flex-wrap items-center gap-x-6 gap-y-2 !rounded-2xl px-5 py-3 text-[12.5px]">
        <span className="inline-flex items-center gap-2 font-semibold"><Info className="size-4 text-sky-300" /> Chỉ dòng có miền ở B và C trống</span>
        <span className="inline-flex items-center gap-1.5 text-emerald-200/90"><ShieldCheck className="size-4" /> Ghi C chỉ khi https:// chạy thật (200 + chứng chỉ hợp lệ)</span>
        <span className="inline-flex items-center gap-1.5 text-rose-200/80"><FileX2 className="size-4" /> Không sửa B · không ghi đè C đã có</span>
        <span className="inline-flex items-center gap-1.5 text-sky-200/90"><Plug className="size-4" /> 100% qua API (AI + cPanel) · không điều khiển trình duyệt</span>
      </div>

      {live.length > 0 && (
        <button
          onClick={() => dispatch({ type: "select", row: live[0].row })}
          className="panel flex w-full items-center gap-3 !rounded-2xl !border-amber-400/30 px-5 py-3 text-left text-[12.5px] text-amber-100"
        >
          <Boxes className="size-4 shrink-0 text-amber-300" />
          <span><b>{live.length} website đang chạy nhưng chưa ghi vào Sheet</b> (ô C bị xung đột): {live.map((r) => r.liveNotWritten!.url).join(", ")} — bấm để xử lý.</span>
        </button>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
        <section className="panel p-5">
          <header className="mb-4 flex items-start justify-between gap-3">
            <div className="flex items-start gap-3">
              <span className="grid size-10 place-items-center rounded-xl bg-sky-500/15 text-sky-200"><Sheet className="size-5" /></span>
              <div>
                <div className="flex items-center gap-2"><h2 className="text-[16px] font-semibold">Quét Google Sheet</h2><SimTag /></div>
                <p className="text-[12.5px] text-fg-muted">Tab Phoi US · đọc qua Google Sheets API (mô phỏng)</p>
              </div>
            </div>
          </header>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Tổng dòng" value={scan.total} />
            <Stat label="B trống — chờ Tạo miền" value={scan.noB} muted />
            <Stat label="C đã có — bỏ qua" value={scan.hasC} muted />
            <Stat label="Đủ điều kiện dựng web" value={state.rows.length} accent />
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 text-[12px] md:grid-cols-3">
            <Info2 icon={<Filter className="size-3.5" />} title="Điều kiện">B có miền · C trống · B thuộc miền gốc của một nick (biết hosting)</Info2>
            <Info2 title="Nhận diện ngành">{autoCount} dòng tự nhận diện · {fallback} không khớp từ khoá (dùng Corporate Firm — nên xem lại)</Info2>
            <Info2 title="Hosting">{noHost ? `${noHost} dòng không rõ hosting — bị chặn` : "Mọi dòng đều xác định được hosting từ danh sách miền của nick"}</Info2>
          </div>
        </section>
        <WebRunPanel state={state} dispatch={dispatch} onPreview={() => setConfirm(true)} />
      </div>

      <TemplateGallery state={state} dispatch={dispatch} />

      <div className="grid grid-cols-1 gap-5 min-[1500px]:grid-cols-[minmax(0,1fr)_420px]">
        <WebTable state={state} dispatch={dispatch} />
        <WebDetail state={state} dispatch={dispatch} />
      </div>

      {confirm && <WebConfirmDialog state={state} dispatch={dispatch} onClose={() => setConfirm(false)} />}
    </div>
  );
}

function Stat({ label, value, muted, accent }: { label: string; value: number; muted?: boolean; accent?: boolean }) {
  return (
    <div className="rounded-xl border border-line bg-ink-850/60 px-4 py-3">
      <div className="text-[11.5px] text-fg-subtle">{label}</div>
      <div className={accent ? "mt-0.5 text-[26px] font-bold text-emerald-300" : muted ? "mt-0.5 text-[26px] font-bold text-fg-muted" : "mt-0.5 text-[26px] font-bold"}>{value}</div>
    </div>
  );
}

function Info2({ title, children, icon }: { title: string; children: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line/70 bg-ink-850/40 px-3.5 py-2.5">
      <div className="mb-0.5 flex items-center gap-1.5 font-semibold text-fg">{icon}{title}</div>
      <div className="text-fg-muted">{children}</div>
    </div>
  );
}
