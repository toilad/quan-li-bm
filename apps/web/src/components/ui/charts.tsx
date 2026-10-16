/** Small inline-SVG charts used on the dashboard (no chart library). */

export function SparkBars({ values, color }: { values: number[]; color: string }) {
  const max = Math.max(...values);
  const w = 7;
  const gap = 5;
  const h = 44;
  return (
    <svg width={values.length * (w + gap) - gap} height={h} aria-hidden>
      {values.map((v, i) => {
        const bh = Math.max(4, (v / max) * h);
        const last = i === values.length - 1;
        return (
          <rect
            key={i}
            x={i * (w + gap)}
            y={h - bh}
            width={w}
            height={bh}
            rx={2.5}
            fill={color}
            opacity={last ? 1 : 0.35 + (i / values.length) * 0.4}
          />
        );
      })}
    </svg>
  );
}

export function Ring({ value, color, size = 64 }: { value: number; color: string; size?: number }) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, value));
  return (
    <svg width={size} height={size} className="-rotate-90" aria-hidden>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="rgb(129 140 248 / 0.14)" strokeWidth={stroke} fill="none" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        fill="none"
        strokeDasharray={c}
        strokeDashoffset={c - (pct / 100) * c}
        style={{ transition: "stroke-dashoffset 600ms ease" }}
      />
    </svg>
  );
}
