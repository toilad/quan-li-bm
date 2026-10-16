/**
 * PDF Manager — types, validation and DEMO DATA for the Phase 1 prototype.
 * Nothing here reads a real PDF or touches Google; the backend comes in Phase 4.
 */

export type FieldKey = "A" | "D" | "E" | "F" | "G" | "H" | "I" | "J";
export type FieldSource = "text" | "ai" | "auto" | "manual" | "missing";
export type Field = { value: string; source: FieldSource; confidence?: number };
export type Fields = Record<FieldKey, Field>;

export const FIELD_META: { key: FieldKey; label: string; hint: string; required: boolean; wide?: boolean }[] = [
  { key: "A", label: "Tên doanh nghiệp", hint: "Giữ nguyên hậu tố LLC / Inc.", required: true, wide: true },
  { key: "D", label: "Số điện thoại", hint: "(XXX) XXX-XXXX", required: true },
  { key: "E", label: "Tên rút gọn", hint: "Tự sinh từ A (giữ LLC)", required: true },
  { key: "F", label: "Địa chỉ", hint: "Số nhà, tên đường", required: true, wide: true },
  { key: "G", label: "Thành phố", hint: "", required: true },
  { key: "H", label: "Bang", hint: "2 chữ cái", required: true },
  { key: "I", label: "ZIP", hint: "5 số", required: true },
  { key: "J", label: "Mã đăng ký", hint: "Đúng như in trên phôi", required: true },
];

export type PdfStatus = "queued" | "processing" | "review" | "saving" | "saved" | "failed" | "duplicate";

export const PROCESS_STEPS = ["Đọc PDF", "Trích xuất", "Kiểm tra trùng"] as const;
/** Drive first, then one append that already carries K — never leaves a half-written row. */
export const SAVE_STEPS = ["Upload PDF gốc lên Drive", "Đối chiếu md5 bản gốc", "Kiểm tra trùng lần cuối", "Ghi dòng mới A, D–K"] as const;

export type DriveState = "none" | "uploading" | "verified" | "failed";

export type PdfFile = {
  id: string;
  name: string;
  sizeKb: number;
  pages: number;
  md5: string;
  status: PdfStatus;
  step: number; // index into PROCESS_STEPS or SAVE_STEPS depending on status
  progress: number; // 0..100 within the current phase
  fields: Fields | null;
  textLayer: boolean; // false = scanned, needs AI/OCR to read
  error?: string;
  duplicateOf?: { row: number; name: string; reason: string };
  sheetRow?: number;
  driveLink?: string;
  drive: DriveState;
  confirmMissing?: boolean;
  /** Demo only: what the fake pipeline ends in. */
  outcome?: "review" | "failed" | "duplicate";
  /** Present for files the user picked in this browser session (preview only, never uploaded). */
  blobUrl?: string;
  local?: boolean;
};

const f = (value: string, source: FieldSource = "text", confidence = 99): Field =>
  value ? { value, source, confidence } : { value: "", source: "missing" };

/** Legacy column E rule: lowercase, keep the legal suffix, strip everything else. */
export const shortName = (a: string) => a.toLowerCase().replace(/[^a-z0-9]/g, "");

function fields(a: string, d: string, street: string, city: string, zip: string, j: string, overrides: Partial<Fields> = {}): Fields {
  return {
    A: f(a),
    D: f(d),
    E: a ? { value: shortName(a), source: "auto" } : f(""),
    F: f(street),
    G: f(city),
    H: f("WY"),
    I: f(zip),
    J: f(j),
    ...overrides,
  };
}

const md5 = (seed: number) =>
  Array.from({ length: 32 }, (_, i) => "0123456789abcdef"[(seed * 7 + i * 13 + ((seed * i) % 11)) % 16]).join("");

export const MOCK_FILES: PdfFile[] = [
  {
    id: "p1", name: "2024-001312455-articles.pdf", sizeKb: 284, pages: 2, md5: md5(1), status: "saved", step: 3, progress: 100,
    fields: fields("Bighorn Basin Roofing LLC", "(307) 555-0412", "418 Grand Ave", "Laramie", "82070", "2024-001312455"),
    textLayer: true, sheetRow: 43, driveLink: "https://drive.google.com/file/d/demo-p1/view", drive: "verified",
  },
  {
    id: "p2", name: "shoshone-ridge-consulting.pdf", sizeKb: 196, pages: 1, md5: md5(2), status: "saved", step: 3, progress: 100,
    fields: fields("Shoshone Ridge Consulting LLC", "(307) 555-0187", "2210 Warren Ave", "Cheyenne", "82001", "2024-001298730"),
    textLayer: true, sheetRow: 44, driveLink: "https://drive.google.com/file/d/demo-p2/view", drive: "verified",
  },
  {
    id: "p3", name: "hoback-creek-dental.pdf", sizeKb: 352, pages: 3, md5: md5(3), status: "saved", step: 3, progress: 100,
    fields: fields("Hoback Creek Dental PLLC", "(307) 555-0349", "75 Snow King Ave", "Jackson", "83001", "2024-001305512"),
    textLayer: true, sheetRow: 45, driveLink: "https://drive.google.com/file/d/demo-p3/view", drive: "verified",
  },
  {
    id: "p4", name: "Absaroka Software Labs - Articles.pdf", sizeKb: 241, pages: 2, md5: md5(4), status: "review", step: 2, progress: 100,
    fields: fields("Absaroka Software Labs LLC", "(307) 555-0623", "1401 Sheridan Ave", "Cody", "82414", "2024-001331087"),
    textLayer: true, drive: "none",
  },
  {
    id: "p5", name: "medicine-wheel-herbal.pdf", sizeKb: 1180, pages: 1, md5: md5(5), status: "review", step: 2, progress: 100,
    // Scanned file: every value comes from AI reading the image, with its confidence.
    fields: fields("Medicine Wheel Herbal Co LLC", "(307) 555-07", "92 Main St", "Sheridan", "", "2024-001327764", {
      A: { value: "Medicine Wheel Herbal Co LLC", source: "ai", confidence: 97 },
      D: { value: "(307) 555-07", source: "ai", confidence: 58 },
      F: { value: "92 Main St", source: "ai", confidence: 86 },
      G: { value: "Sheridan", source: "ai", confidence: 95 },
      H: { value: "WY", source: "ai", confidence: 99 },
      J: { value: "2024-001327764", source: "ai", confidence: 94 },
    }),
    textLayer: false, drive: "none",
  },
  {
    id: "p6", name: "sinks-canyon-builders.pdf", sizeKb: 305, pages: 2, md5: md5(6), status: "processing", step: 1, progress: 40,
    fields: null, textLayer: true, drive: "none", outcome: "review",
  },
  {
    id: "p7", name: "green-river-freight-annual.pdf", sizeKb: 220, pages: 2, md5: md5(7), status: "processing", step: 0, progress: 70,
    fields: null, textLayer: true, drive: "none", outcome: "review",
  },
  {
    id: "p8", name: "laramie-legal-annual-report.pdf", sizeKb: 188, pages: 1, md5: md5(8), status: "duplicate", step: 2, progress: 100,
    fields: fields("Laramie Legal Group LLC", "(307) 555-0159", "379 Lincolnway", "Riverton", "82501", "2024-001292774"),
    textLayer: true, drive: "none",
    duplicateOf: { row: 10, name: "Laramie Legal Group LLC", reason: "Trùng mã đăng ký J + bang WY" },
  },
  {
    id: "p9", name: "scan_0021232316.pdf", sizeKb: 2240, pages: 1, md5: md5(9), status: "failed", step: 1, progress: 100,
    fields: null, textLayer: false, drive: "none",
    error: "PDF là bản scan mờ — AI chỉ đọc được 31% nội dung, không xác định được tên công ty. Không tự điền.",
  },
  { id: "p10", name: "vedauwoo-media-group.pdf", sizeKb: 274, pages: 2, md5: md5(10), status: "queued", step: 0, progress: 0, fields: null, textLayer: true, drive: "none", outcome: "review" },
  { id: "p11", name: "glendo-lake-realty.pdf", sizeKb: 233, pages: 1, md5: md5(11), status: "queued", step: 0, progress: 0, fields: null, textLayer: true, drive: "none", outcome: "review" },
  { id: "p12", name: "encampment-outfitters.pdf", sizeKb: 3010, pages: 4, md5: md5(12), status: "queued", step: 0, progress: 0, fields: null, textLayer: false, drive: "none", outcome: "failed" },
];

/** Demo extraction results for queued/processing mock files (keyed by id). */
export const MOCK_RESULTS: Record<string, Fields> = {
  p6: fields("Sinks Canyon Builders LLC", "(307) 555-0291", "530 Main St", "Lander", "82520", "2024-001334410"),
  p7: fields("Green River Freight LLC", "(307) 555-0718", "1188 Dewar Dr", "Rock Springs", "82901", "2024-001335902"),
  p10: fields("Vedauwoo Media Group LLC", "(307) 555-0832", "605 S 3rd St", "Laramie", "82070", "2024-001337156"),
  p11: fields("Glendo Lake Realty LLC", "", "212 Yellowstone Hwy", "Glendo", "82213", "2024-001338049", {
    D: { value: "", source: "missing" },
  }),
};

export type Issue = { level: "error" | "warn"; msg: string };

export function validate(fieldsIn: Fields): Partial<Record<FieldKey, Issue>> {
  const out: Partial<Record<FieldKey, Issue>> = {};
  for (const m of FIELD_META) {
    const v = fieldsIn[m.key].value.trim();
    if (!v) {
      out[m.key] = { level: "error", msg: "Không tìm thấy trong PDF — không tự điền" };
      continue;
    }
    const digits = v.replace(/\D/g, "");
    if (m.key === "D" && digits.length !== 10 && digits.length !== 11) out.D = { level: "error", msg: "Số điện thoại chưa đủ 10 số" };
    if (m.key === "H" && !/^[A-Z]{2}$/.test(v)) out.H = { level: "error", msg: "Bang phải là 2 chữ in hoa (vd: WY)" };
    if (m.key === "I" && !/^\d{5}(-\d{4})?$/.test(v)) out.I = { level: "error", msg: "ZIP phải có 5 số" };
    const fld = fieldsIn[m.key];
    if (!out[m.key] && fld.source === "ai" && (fld.confidence ?? 100) < 80)
      out[m.key] = { level: "warn", msg: `AI đọc với độ tin cậy ${fld.confidence}% — cần kiểm tra lại` };
  }
  return out;
}

export const emptyFields = (): Fields => ({
  A: f(""), D: f(""), E: f(""), F: f(""), G: f(""), H: f(""), I: f(""), J: f(""),
});

export const SHEET_TABS = ["Phoi US", "Tinh Tool"] as const;
