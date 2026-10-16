/**
 * SSL + Website Builder — rules and DEMO DATA for the Phase 1 prototype.
 *
 * For each Sheet row with a domain in B and an empty C: detect the industry,
 * pick one of the 15 legacy templates, write the pages with an AI API, build the
 * HTML, upload it to the hosting that serves B (cPanel API), start AutoSSL, and
 * only when https://B answers correctly write the URL to C. Nothing here calls
 * Google, AI, iNET or cPanel.
 */
import { COMPANIES, type Company } from "./mock-data";
import { isEligibleForWebsite } from "./sheet-rules";
import { TEMPLATES, TEMPLATE_BY_ID, type SiteTemplate } from "./templates";
import { NICKS, findRoot, type Nick, type RootDomain } from "./domain-mock";

/* ───────── Industry detection ───────── */

export type Detection = {
  template: SiteTemplate;
  /** Keyword from the company name that matched; null = no match, fell back to Corporate Firm. */
  keyword: string | null;
};

/** Same rule as detectTemplate, but says why — the owner sees what matched before approving. */
export function detectWithReason(name: string): Detection {
  const words = name.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  for (const t of TEMPLATES) {
    if (t.id === "corporate-firm") continue;
    const k = t.industries.find((ind) => words.some((w) => w.startsWith(ind)));
    if (k) return { template: t, keyword: k };
  }
  const corp = TEMPLATE_BY_ID["corporate-firm"];
  const k = corp.industries.find((ind) => words.some((w) => w.startsWith(ind)));
  return { template: corp, keyword: k ?? null };
}

/* ───────── Pipeline ───────── */

export const WEB_STEPS = [
  "Kiểm tra DNS của B trỏ đúng IP hosting",
  "Xác minh document root trên cPanel (API)",
  "Tạo nội dung bằng AI API",
  "Kiểm tra nội dung (không bịa)",
  "Dựng HTML theo mẫu",
  "Upload lên hosting (cPanel API)",
  "Bật SSL (AutoSSL qua API)",
  "Kiểm tra HTTPS",
  "Đọc lại ô C → ghi C",
] as const;

/** Pages built for every site — the legacy src/templates set (base = shared layout). */
export const SITE_PAGES = ["Trang chủ", "Giới thiệu", "Liên hệ", "Hỏi đáp", "Chính sách bảo mật", "Điều khoản"] as const;

export type WebStatus = "idle" | "queued" | "running" | "done" | "failed" | "conflict";
export type LogLine = { t: string; msg: string; tone: "ok" | "err" | "info" | "warn" };

export type WebRow = {
  row: number;
  company: Company;
  domain: string; // column B — read only
  /** Root + nick that serve B, found from the synced domain lists; null = unknown hosting (blocked). */
  host: { nick: Nick; root: RootDomain } | null;
  detection: Detection;
  templateId: string;
  templateSource: "auto" | "manual";
  status: WebStatus;
  step: number;
  progress: number;
  /** Steps already done stay done on retry (content, upload) — never redone or duplicated. */
  contentReady: boolean;
  uploaded: boolean;
  sslIssued: boolean;
  /**
   * Document root of B as cPanel reports it (relative to the account home) — read over the API before
   * uploading, never assumed. Subdomain: SubDomain::listsubdomains → basedir; main/addon:
   * DomainInfo::single_domain_data → documentroot. Unset until read.
   */
  docRoot?: string;
  docRootApi?: string;
  /** Template the HTML was actually built with — must equal templateId. */
  builtTemplate?: string;
  error?: string;
  writtenC?: string;
  /** Live HTTPS site whose C cell was taken meanwhile — kept for the owner to resolve. */
  liveNotWritten?: { url: string; foundC: string; at: string; resolved?: string };
  log: LogLine[];
  checked: boolean;
  /** Demo only: scripted behaviour for this row. */
  outcome?: "aiRegenerate" | "sslPendingOnce" | "dnsMismatch" | "conflictAtWrite" | "notOnCpanel";
  /** Demo only: the document root cPanel will report for this domain. */
  demoDocRoot?: string;
};

/** What cPanel reports for B in the demo: most subdomains under public_html, some elsewhere. */
export const demoDocRootFor = (r: WebRow) => r.demoDocRoot ?? `public_html/${r.domain}`;

export const hostOf = (domain: string, nicks: Nick[] = NICKS) => {
  for (const nick of nicks)
    for (const root of nick.roots) if (domain.endsWith(`.${root.name}`)) return findRoot(root.name, nicks);
  return null;
};

/** Rows with a domain in B and an empty C. Anything else is counted, never processed. */
export function scanForWeb() {
  const eligible = COMPANIES.filter(isEligibleForWebsite);
  return {
    total: COMPANIES.length,
    noB: COMPANIES.filter((c) => !c.B.trim()).length,
    hasC: COMPANIES.filter((c) => c.C.trim()).length,
    eligible,
  };
}

export function initialWebRows(): WebRow[] {
  return scanForWeb().eligible.map((c, idx): WebRow => {
    const detection = detectWithReason(c.A);
    const manual = c.templateSource === "manual";
    const base: WebRow = {
      row: c.row, company: c, domain: c.B, host: hostOf(c.B), detection,
      templateId: manual ? c.template.id : detection.template.id, templateSource: manual ? "manual" : "auto",
      status: "idle", step: 0, progress: 0, contentReady: false, uploaded: false, sslIssued: false, log: [], checked: false,
    };
    // Scripted demo cases, each showing one safety rule.
    if (c.stages.domain === "conflict") base.outcome = "dnsMismatch"; // B was typed by someone else
    else if (c.stages.web === "error") base.outcome = "sslPendingOnce";
    else if (idx === 1) base.outcome = "aiRegenerate";
    else if (idx === 4) base.outcome = "conflictAtWrite";
    else if (idx === 6) base.outcome = "notOnCpanel"; // B written by hand, never created on the hosting
    // Created by hand outside public_html — the upload must follow what cPanel says, not a fixed path.
    if (idx === 3) base.demoDocRoot = `sites/${c.B.split(".")[0]}`;
    // A past failure stays visible; nothing is queued or running on open.
    if (c.stages.web === "error")
      return {
        ...base, status: "failed", step: 6, progress: 100, contentReady: true, uploaded: true, outcome: undefined, // already failed once; the retry succeeds
        docRoot: `public_html/${c.B}`, docRootApi: "SubDomain::listsubdomains", builtTemplate: base.templateId,
        error: "AutoSSL chưa cấp chứng chỉ — HTTPS chưa truy cập được. C giữ trống. Thử lại sau khi DNS ổn định (~40 phút).",
        log: [
          { t: "14:18:02", msg: "Nội dung AI đạt kiểm tra · đã dựng 6 trang", tone: "ok" },
          { t: "14:17:51", msg: "cPanel SubDomain::listsubdomains: document root ~/public_html/" + c.B, tone: "ok" },
          { t: "14:18:40", msg: "Upload xong ~/public_html/" + c.B, tone: "ok" },
          { t: "14:22:15", msg: "AutoSSL: chưa cấp chứng chỉ → dừng, C giữ trống", tone: "err" },
        ],
      };
    return base;
  });
}

/* ───────── Content shown in the preview (what the AI is allowed to use) ───────── */

/** Facts the AI may state — all read from the Sheet. Everything else is generic copy, never awards/clients/numbers. */
export function sheetFacts(c: Company) {
  return [
    ["Tên doanh nghiệp (A)", c.A],
    ["Điện thoại (D)", c.D],
    ["Địa chỉ (F–I)", `${c.F}, ${c.G}, ${c.H} ${c.I}`.trim()],
    ["Mã đăng ký (J)", c.J],
  ] as const;
}

export const CONTENT_RULES = [
  "Không bịa giải thưởng, khách hàng, đối tác, số năm hoạt động hay số liệu",
  "Thông tin liên hệ chỉ lấy từ Sheet (A, D, F–I) — thiếu thì để trống, không tự điền",
  "Dịch vụ viết chung theo ngành, không hứa hẹn kết quả",
  "Kết quả AI phải đúng cấu trúc JSON cố định; sai → tạo lại, tối đa 2 lần",
];
