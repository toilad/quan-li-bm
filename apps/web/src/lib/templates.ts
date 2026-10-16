/**
 * The 15 named website templates recovered from the legacy WebsiteGenerator
 * (src/config.py in the old EXE), with their photo keywords, plus the
 * industry-detection rules from the old ai_generator prompt.
 *
 * Industry -> template mapping below is a PROPOSAL pending owner approval.
 */

export type TemplateGroup =
  | "Doanh nghiệp & Dịch vụ"
  | "Xây dựng & Kiến trúc"
  | "Công nghệ"
  | "Truyền thông"
  | "Y tế & Làm đẹp"
  | "Pháp lý & Tài chính"
  | "Giáo dục"
  | "Du lịch"
  | "Thương mại"
  | "Môi trường & Nông nghiệp";

export type TemplateIcon =
  | "briefcase" | "users" | "building" | "cpu" | "clapperboard" | "sparkles" | "smile"
  | "scale" | "shield" | "graduation" | "book" | "plane" | "leaf" | "recycle" | "trees";

export type HeroLayout = "centered" | "split-left" | "split-right" | "minimal" | "stacked-cards" | "image-banner";

export type SiteTemplate = {
  id: string;
  name: string;
  group: TemplateGroup;
  icon: TemplateIcon;
  primary: string; // accent colour from the legacy palette
  accent: string;
  hero: HeroLayout;
  photoKeywords: string[]; // verbatim from the legacy config
  industries: string[]; // detection keywords (company name / business type)
};

export const TEMPLATES: SiteTemplate[] = [
  { id: "corporate-firm", name: "Corporate Firm", group: "Doanh nghiệp & Dịch vụ", icon: "briefcase", primary: "#2563eb", accent: "#93c5fd", hero: "split-left", photoKeywords: ["office", "corporate", "business", "meeting"], industries: ["consulting", "holding", "group", "partners", "freight", "logistic", "realty", "auto", "motor", "hvac", "plumb", "electric"] },
  { id: "hr-management", name: "HR Management", group: "Doanh nghiệp & Dịch vụ", icon: "users", primary: "#0d9488", accent: "#5eead4", hero: "stacked-cards", photoKeywords: ["people", "office", "teamwork", "handshake"], industries: ["hr", "staffing", "recruit", "workforce"] },
  { id: "misbah-architecture", name: "Misbah Architecture Blocks", group: "Xây dựng & Kiến trúc", icon: "building", primary: "#d97706", accent: "#fcd34d", hero: "image-banner", photoKeywords: ["architecture", "building", "modern", "interior"], industries: ["construction", "builder", "carpentry", "architecture", "roofing", "concrete"] },
  { id: "blockskit-digital", name: "Blockskit Digital Agency Firm", group: "Công nghệ", icon: "cpu", primary: "#7c3aed", accent: "#c4b5fd", hero: "split-right", photoKeywords: ["technology", "office", "startup", "design"], industries: ["tech", "software", "digital", "data", "systems", "cloud"] },
  { id: "daily-soap-tv", name: "Daily SOAP TV", group: "Truyền thông", icon: "clapperboard", primary: "#c026d3", accent: "#f0abfc", hero: "centered", photoKeywords: ["studio", "media", "broadcasting", "camera"], industries: ["media", "film", "tv", "broadcast", "production"] },
  { id: "dermatologist-clinic", name: "Dermatologist Clinic", group: "Y tế & Làm đẹp", icon: "sparkles", primary: "#e11d48", accent: "#fda4af", hero: "split-left", photoKeywords: ["skincare", "dermatology", "spa", "beauty"], industries: ["dermat", "skin", "salon", "spa", "beauty", "wellness", "clinic", "medic", "health", "pharm"] },
  { id: "fse-dental", name: "FSE Dental Clinic", group: "Y tế & Làm đẹp", icon: "smile", primary: "#0284c7", accent: "#7dd3fc", hero: "minimal", photoKeywords: ["dental", "dentist", "smile", "teeth"], industries: ["dental", "dds", "dentist", "orthodont"] },
  { id: "lawyer-legal", name: "Lawyer Legal Firm", group: "Pháp lý & Tài chính", icon: "scale", primary: "#1e3a8a", accent: "#a5b4fc", hero: "split-right", photoKeywords: ["law", "courthouse", "justice", "books"], industries: ["law", "legal", "attorney", "counsel"] },
  { id: "spike-insurance", name: "Spike Insurance", group: "Pháp lý & Tài chính", icon: "shield", primary: "#4f46e5", accent: "#a5b4fc", hero: "stacked-cards", photoKeywords: ["family", "office", "security", "protection"], industries: ["insurance", "finance", "capital", "invest"] },
  { id: "wens-academy", name: "WENS Academy", group: "Giáo dục", icon: "graduation", primary: "#0891b2", accent: "#67e8f9", hero: "centered", photoKeywords: ["education", "students", "classroom", "learning"], industries: ["academy", "school", "education", "training", "tutor"] },
  { id: "online-library", name: "Online Library", group: "Giáo dục", icon: "book", primary: "#ea580c", accent: "#fdba74", hero: "minimal", photoKeywords: ["books", "library", "reading", "knowledge"], industries: ["book", "library", "publish"] },
  { id: "expert-travel", name: "Expert Travel Agent", group: "Du lịch", icon: "plane", primary: "#0284c7", accent: "#7dd3fc", hero: "image-banner", photoKeywords: ["travel", "beach", "destination", "vacation"], industries: ["travel", "tour", "outfitter", "adventure", "lodge"] },
  { id: "herbal-shop", name: "Herbal Products Shop", group: "Thương mại", icon: "leaf", primary: "#059669", accent: "#6ee7b7", hero: "split-left", photoKeywords: ["herbs", "plants", "wellness", "nature"], industries: ["herbal", "shop", "store", "trading", "coffee", "bakery", "roaster", "goods"] },
  { id: "waste-management", name: "Waste Management Firm", group: "Môi trường & Nông nghiệp", icon: "recycle", primary: "#65a30d", accent: "#bef264", hero: "split-right", photoKeywords: ["environment", "recycling", "green", "nature"], industries: ["waste", "recycl", "environment", "mining", "oil", "gas", "clean"] },
  { id: "tree-plantation", name: "Tree Plantation", group: "Môi trường & Nông nghiệp", icon: "trees", primary: "#16a34a", accent: "#86efac", hero: "image-banner", photoKeywords: ["forest", "trees", "nature", "green"], industries: ["ranch", "farm", "cattle", "tree", "orchard", "vineyard", "livestock"] },
];

export const TEMPLATE_BY_ID = Object.fromEntries(TEMPLATES.map((t) => [t.id, t])) as Record<string, SiteTemplate>;

/**
 * Deterministic industry detection: first template with a keyword that starts
 * a word of the company name wins; otherwise Corporate Firm. Never random.
 */
export function detectTemplate(companyName: string): SiteTemplate {
  const words = companyName.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
  const specific = TEMPLATES.filter((t) => t.id !== "corporate-firm");
  return (
    specific.find((t) => t.industries.some((k) => words.some((w) => w.startsWith(k)))) ??
    TEMPLATE_BY_ID["corporate-firm"]
  );
}
