import {
  Briefcase, Users, Building2, Cpu, Clapperboard, Sparkles, Smile, Scale, ShieldCheck, GraduationCap, BookOpen,
  Plane, Leaf, Recycle, Trees, type LucideIcon,
} from "lucide-react";
import type { SiteTemplate, TemplateIcon } from "@/lib/templates";

export const TEMPLATE_ICONS: Record<TemplateIcon, LucideIcon> = {
  briefcase: Briefcase, users: Users, building: Building2, cpu: Cpu, clapperboard: Clapperboard, sparkles: Sparkles,
  smile: Smile, scale: Scale, shield: ShieldCheck, graduation: GraduationCap, book: BookOpen, plane: Plane,
  leaf: Leaf, recycle: Recycle, trees: Trees,
};

/**
 * Miniature website preview drawn from the template's palette and hero
 * layout. Real screenshots replace this once the renderer exists.
 */
export function TemplateThumb({ t }: { t: SiteTemplate }) {
  const Icon = TEMPLATE_ICONS[t.icon];
  const photo = (
    <div
      className="relative grid h-full w-full place-items-center overflow-hidden rounded-md"
      style={{ background: `linear-gradient(135deg, ${t.primary}, ${t.accent})` }}
    >
      <div className="absolute inset-0 opacity-25" style={{ backgroundImage: "radial-gradient(circle at 30% 20%, white 0 2px, transparent 3px)", backgroundSize: "18px 18px" }} />
      <Icon className="relative size-8 text-white/90 drop-shadow" strokeWidth={1.6} />
    </div>
  );
  const text = (
    <div className="flex flex-col justify-center gap-1.5">
      <div className="h-1.5 w-10 rounded-full" style={{ background: t.primary }} />
      <div className="h-2.5 w-full rounded-sm bg-slate-800" />
      <div className="h-2.5 w-3/4 rounded-sm bg-slate-800" />
      <div className="mt-0.5 h-1.5 w-full rounded-sm bg-slate-300" />
      <div className="h-1.5 w-5/6 rounded-sm bg-slate-300" />
      <div className="mt-1 h-3.5 w-12 rounded" style={{ background: t.primary }} />
    </div>
  );

  let hero: React.ReactNode;
  switch (t.hero) {
    case "image-banner":
    case "centered":
      hero = (
        <div className="relative h-full">
          {photo}
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 bg-black/25">
            <div className="h-2.5 w-28 rounded-sm bg-white/95" />
            <div className="h-1.5 w-20 rounded-sm bg-white/70" />
            <div className="mt-1 h-3.5 w-12 rounded bg-white" />
          </div>
        </div>
      );
      break;
    case "split-right":
      hero = <div className="grid h-full grid-cols-2 gap-3">{photo}{text}</div>;
      break;
    case "stacked-cards":
      hero = (
        <div className="grid h-full grid-cols-[1.1fr_1fr] gap-3">
          {text}
          <div className="relative">
            <div className="absolute inset-y-1 left-2 right-0 rotate-3 rounded-md opacity-40" style={{ background: t.accent }} />
            <div className="relative h-full">{photo}</div>
          </div>
        </div>
      );
      break;
    case "minimal":
      hero = (
        <div className="flex h-full flex-col justify-center gap-2 px-4">
          <div className="h-3 w-3/4 rounded-sm bg-slate-800" />
          <div className="h-1.5 w-1/2 rounded-sm bg-slate-300" />
          <div className="mt-1 grid grid-cols-3 gap-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-8 rounded-md" style={{ background: i === 1 ? t.primary : `${t.accent}66` }} />
            ))}
          </div>
        </div>
      );
      break;
    default:
      hero = <div className="grid h-full grid-cols-2 gap-3">{text}{photo}</div>;
  }

  return (
    <div className="aspect-[16/10] w-full overflow-hidden rounded-xl bg-white shadow-inner">
      <div className="flex h-[14%] items-center justify-between border-b border-slate-200 px-3">
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: t.primary }} />
          <span className="h-1.5 w-10 rounded-sm bg-slate-700" />
        </div>
        <div className="flex gap-1.5">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="h-1 w-5 rounded-sm bg-slate-300" />
          ))}
        </div>
      </div>
      <div className="h-[62%] p-3">{hero}</div>
      <div className="grid h-[24%] grid-cols-3 gap-2 bg-slate-50 px-3 py-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="rounded-md border border-slate-200 bg-white p-1.5">
            <div className="mb-1 size-2.5 rounded-sm" style={{ background: t.accent }} />
            <div className="h-1 w-full rounded-sm bg-slate-300" />
          </div>
        ))}
      </div>
    </div>
  );
}
