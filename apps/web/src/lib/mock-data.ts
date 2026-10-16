/**
 * DEMO DATA ONLY — fake Wyoming companies used by the Phase 1 design
 * prototype. Nothing here comes from a real sheet or account.
 */
import { detectTemplate, type SiteTemplate } from "./templates";
import type { ModuleKey, SheetRow } from "./sheet-rules";

export type StageStatus = "done" | "running" | "queued" | "error" | "conflict" | "idle";

export type Company = SheetRow & {
  template: SiteTemplate;
  templateSource: "auto" | "manual";
  stages: Record<ModuleKey, StageStatus>;
  note?: string;
};

const NAMES = [
  "N Triangle Ranch, Inc.", "Global Freight Partners LLC", "13570 Tradition Street LLC", "Summit Peak Construction LLC",
  "Bluewave Software Solutions LLC", "Cheyenne Dental Studio PLLC", "Red Canyon Logistics LLC", "Laramie Legal Group LLC",
  "Sweetwater Realty LLC", "Teton Coffee Roasters LLC", "Big Horn HVAC Services LLC", "Prairie Rose Salon LLC",
  "Frontier Auto Works LLC", "Wind River Media Studio LLC", "Casper Health Clinic LLC", "Powder River Mining Co LLC",
  "Granite Ridge Builders LLC", "Yellowstone Travel Co LLC", "Medicine Bow Academy LLC", "Sheridan Herbal Co LLC",
  "Pinedale Insurance Agency LLC", "Evergreen Tree Farm LLC", "Clearwater Waste Solutions LLC", "Bridger HR Partners LLC",
  "Rock Springs Digital LLC", "Lander Dermatology LLC", "Riverton Book House LLC", "Gillette Electric LLC",
  "Jackson Hole Outfitters LLC", "Cody Creek Vineyard LLC", "Douglas Freightways LLC", "Thermopolis Wellness Spa LLC",
  "Buffalo Ridge Cattle Co LLC", "Kemmerer Plumbing LLC", "Torrington Motors LLC", "Afton Architecture Studio LLC",
  "Wheatland Consulting Group LLC", "Newcastle Data Systems LLC", "Saratoga Realty Group LLC", "Evanston Roofing LLC",
];

const CITIES = ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan", "Jackson", "Riverton", "Cody", "Evanston"];
const STREETS = ["Capitol Ave", "Warren Ave", "Grand Ave", "Lincolnway", "Pioneer Ave", "Yellowstone Rd", "Snow King Ave", "Main St"];
// Default root domain of each of the owner's 3 iNET accounts (see NICKS in domain-mock.ts). Company rows are still demo data.
const PARENTS = ["sustainlife.io.vn", "ntp88.com", "groupany.id.vn"];

const LEGAL_SUFFIX = /\b(llc|inc|pllc|co|corp|ltd)\b\.?/g;

/** Same idea as the legacy _slug_for_subdomain: 'N Triangle Ranch, Inc.' -> 'ntriangleranch'. */
export const subdomainSlug = (name: string) => name.toLowerCase().replace(LEGAL_SUFFIX, "").replace(/[^a-z0-9]/g, "");
/** Legacy column E "Tên thường": keeps the legal suffix. */
const shortName = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, "");

function stagesFor(i: number): { stages: Record<ModuleKey, StageStatus>; hasB: boolean; hasC: boolean; hasK: boolean; note?: string } {
  if (i < 14) return { stages: { pdf: "done", domain: "done", web: "done" }, hasB: true, hasC: true, hasK: true };
  if (i < 22) {
    const web: StageStatus = i < 16 ? "running" : i === 16 ? "error" : i < 19 ? "queued" : "idle";
    const note = i === 16 ? "AutoSSL chưa cấp chứng chỉ — HTTPS chưa truy cập được. C giữ trống." : undefined;
    if (i === 21)
      return {
        stages: { pdf: "done", domain: "conflict", web: "idle" },
        hasB: true, hasC: false, hasK: true,
        note: "Ô B đã có giá trị khi ghi (người khác nhập) — bỏ qua, không ghi đè.",
      };
    return { stages: { pdf: "done", domain: "done", web }, hasB: true, hasC: false, hasK: true, note };
  }
  if (i < 34) {
    const domain: StageStatus = i < 24 ? "running" : i === 24 ? "error" : i < 28 ? "queued" : "idle";
    const note = i === 24 ? "iNET từ chối: bản ghi đã tồn tại trên miền chính. B giữ trống, có thể thử lại." : undefined;
    return { stages: { pdf: "done", domain, web: "idle" }, hasB: false, hasC: false, hasK: true, note };
  }
  if (i < 38) return { stages: { pdf: "running", domain: "idle", web: "idle" }, hasB: false, hasC: false, hasK: false };
  return {
    stages: { pdf: "error", domain: "idle", web: "idle" },
    hasB: false, hasC: false, hasK: true,
    note: "PDF thiếu mã ZIP — không tự điền, chờ kiểm tra thủ công.",
  };
}

export const COMPANIES: Company[] = NAMES.map((name, i) => {
  const { stages, hasB, hasC, hasK, note } = stagesFor(i);
  const domain = `${subdomainSlug(name)}.${PARENTS[i % PARENTS.length]}`;
  const template = detectTemplate(name);
  return {
    row: i + 3,
    A: name,
    B: hasB ? (stages.domain === "conflict" ? `${subdomainSlug(name)}-old.${PARENTS[0]}` : domain) : "",
    C: hasC ? `https://${domain}` : "",
    D: `(307) 555-${String(110 + i * 7).padStart(4, "0")}`,
    E: shortName(name),
    F: `${120 + i * 37} ${STREETS[i % STREETS.length]}`,
    G: CITIES[i % CITIES.length],
    H: "WY",
    I: i === 38 ? "" : `820${String(1 + (i % 9)).padStart(2, "0")}`,
    J: `2024-00${(1263885 + i * 4127).toString()}`,
    K: hasK ? `https://drive.google.com/file/d/demo${(i * 7919).toString(36)}/view` : "",
    L: "",
    template,
    templateSource: i === 9 || i === 31 ? "manual" : "auto",
    stages,
    note,
  };
});

export type ActivityItem = {
  time: string;
  module: ModuleKey | "system";
  tone: "ok" | "error" | "warn" | "info";
  title: string;
  detail: string;
};

export const ACTIVITY: ActivityItem[] = [
  { time: "14:32", module: "pdf", tone: "ok", title: "Đã xử lý 4 PDF", detail: "Ghi A, D–K · B, C giữ trống · 4 file gốc lên Drive" },
  { time: "14:29", module: "web", tone: "ok", title: "Website hoạt động: windrivermediastudio", detail: "HTTPS 200 · đã ghi cột C" },
  { time: "14:25", module: "domain", tone: "error", title: "Tạo miền thất bại: bridgerhrpartners", detail: "Bản ghi đã tồn tại · B giữ trống" },
  { time: "14:22", module: "web", tone: "warn", title: "Chờ SSL: graniteridgebuilders", detail: "AutoSSL chưa cấp · tự thử lại sau 15 phút" },
  { time: "14:18", module: "domain", tone: "warn", title: "Xung đột ghi cột B dòng 24", detail: "Ô đã có dữ liệu · bỏ qua, không ghi đè" },
  { time: "14:10", module: "pdf", tone: "error", title: "Thiếu trường ZIP: Saratoga Realty Group", detail: "Không tự bịa dữ liệu · chờ kiểm tra" },
  { time: "03:00", module: "system", tone: "ok", title: "Sao lưu tự động hoàn tất", detail: "Database + file · 7 ngày / 4 tuần / 12 tháng" },
];

export const CONNECTIONS = [
  { key: "sheets", label: "Google Sheets", status: "ok" as const, detail: "Tab Phoi US · đồng bộ 2 phút trước" },
  { key: "drive", label: "Drive", status: "ok" as const, detail: "Thư mục Phôi PDF" },
  { key: "inet", label: "iNET", status: "ok" as const, detail: "5 tài khoản" },
  { key: "hosting", label: "Hosting", status: "warn" as const, detail: "1/5 cPanel phản hồi chậm" },
  { key: "ai", label: "AI", status: "ok" as const, detail: "Claude · OpenAI dự phòng" },
];

export const BACKUP = {
  lastRun: "03:00 hôm nay",
  versions: 23,
  retention: "7 ngày · 4 tuần · 12 tháng",
  lastRestoreTest: "01/10 · đạt",
};

/** 7-day trend for the KPI sparkbars (oldest -> newest). */
export const TRENDS = {
  pdf: [18, 22, 19, 27, 24, 31, 36],
  domain: [9, 14, 12, 15, 18, 17, 22],
  web: [6, 8, 11, 9, 12, 13, 14],
  error: [2, 1, 3, 2, 4, 3, 5],
};
