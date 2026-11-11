import { useId } from "react";
import { colors } from "@aurevon/design-tokens";
import styles from "./GarmentArt.module.css";

/**
 * Illustrated garment on a floating hanger: the stand-in for product photography until approved imagery exists
 * (M4 limitation; the catalogue API marks these images as `demo_art`). Drawn in the product's own colour,
 * self-contained SVG, no external requests.
 */
export type ArtKind =
  "dress" | "shirt" | "coat" | "trousers" | "knit" | "blazer" | "kurta" | "skirt";

// Silhouettes in a 200 x 260 box, hanging from a hanger bar at y = 40.
const BODIES: Record<ArtKind, string> = {
  dress: "M78 44 L122 44 L128 70 L120 96 L150 236 Q100 248 50 236 L80 96 L72 70 Z",
  skirt: "M70 46 L130 46 L134 60 L162 232 Q100 244 38 232 L66 60 Z",
  shirt:
    "M70 44 L88 40 Q100 52 112 40 L130 44 L168 70 L156 104 L138 92 L138 196 L62 196 L62 92 L44 104 L32 70 Z",
  kurta:
    "M72 44 L90 40 Q100 50 110 40 L128 44 L160 70 L150 120 L138 112 L146 236 L54 236 L62 112 L50 120 L40 70 Z",
  knit: "M68 46 L88 40 Q100 50 112 40 L132 46 L166 74 L160 168 L144 168 L140 100 L140 192 L60 192 L60 100 L56 168 L40 168 L34 74 Z",
  blazer:
    "M68 44 L90 40 L100 92 L110 40 L132 44 L166 72 L158 176 L142 176 L140 104 L142 204 L58 204 L60 104 L58 176 L42 176 L34 72 Z",
  coat: "M66 44 L90 40 L100 96 L110 40 L134 44 L168 74 L162 196 L146 196 L142 110 L150 240 L50 240 L58 110 L54 196 L38 196 L32 74 Z",
  trousers: "M66 52 L134 52 L140 236 L108 236 L100 112 L92 236 L60 236 Z",
};

// Decorative seams and folds per garment, drawn as light strokes over the fill.
const DETAILS: Record<ArtKind, string> = {
  dress: "M80 96 L120 96 M96 110 L88 230 M106 120 L114 232",
  skirt: "M68 60 L132 60 M92 70 L80 232 M108 70 L118 232",
  shirt: "M100 52 L100 196 M96 70 h-1 M96 100 h-1 M96 130 h-1 M96 160 h-1 M62 180 L138 180",
  kurta: "M100 50 L100 120 M70 200 Q100 210 130 200 M66 216 Q100 226 134 216",
  knit: "M64 100 L136 100 M60 184 L140 184 M100 52 Q100 60 100 52",
  blazer: "M100 92 L100 204 M74 150 L92 150 M108 150 L126 150 M96 120 h-1 M96 140 h-1",
  coat: "M100 96 L100 240 M70 160 L92 160 M108 160 L130 160 M96 124 h-1 M96 150 h-1 M96 176 h-1",
  trousers: "M100 56 L100 112 M70 66 L130 66 M78 70 L72 120",
};

/** Darken (amount < 0) or lighten (amount > 0) a #RRGGBB colour. */
function shade(hex: string, amount: number): string {
  const n = parseInt(hex.slice(1), 16);
  const mix = (c: number) => Math.round(amount < 0 ? c * (1 + amount) : c + (255 - c) * amount);
  const r = mix((n >> 16) & 255);
  const g = mix((n >> 8) & 255);
  const b = mix(n & 255);
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
}

function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  return (0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
}

export function GarmentArt({
  kind,
  colour,
  label,
  float = true,
  stage = "light",
  className,
}: {
  kind: ArtKind;
  colour: string;
  /** Accessible description; omit when a nearby heading already names the product. */
  label?: string;
  float?: boolean;
  /** Light stage for product cards; dark stage for the hero and editorial bands. */
  stage?: "light" | "dark";
  className?: string;
}) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const safe = /^#[0-9a-fA-F]{6}$/.test(colour) ? colour : "#9A958E";
  const light = luminance(safe) > 0.75;
  const detail = light ? shade(safe, -0.25) : shade(safe, 0.18);
  // Gold only on the dark stage (decision 0004: gold is for accents on dark surfaces).
  const hanger = stage === "dark" ? colors.amber : colors.deepIndigo;

  return (
    <svg
      viewBox="0 0 200 260"
      className={[styles.art, float ? styles.float : "", className ?? ""].filter(Boolean).join(" ")}
      focusable="false"
      {...(label ? { role: "img", "aria-label": label } : { "aria-hidden": true })}
      data-art={kind}
    >
      <defs>
        <linearGradient id={`fabric-${id}`} x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stopColor={shade(safe, 0.12)} />
          <stop offset="0.55" stopColor={safe} />
          <stop offset="1" stopColor={shade(safe, -0.22)} />
        </linearGradient>
        <radialGradient id={`shadow-${id}`}>
          <stop offset="0" stopColor="#000" stopOpacity={stage === "dark" ? 0.45 : 0.16} />
          <stop offset="1" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse
        className={styles.shadow}
        cx="100"
        cy="252"
        rx="58"
        ry="6"
        fill={`url(#shadow-${id})`}
      />
      <g className={styles.garment}>
        {/* Hanger: hook, shoulders, bar */}
        <path
          d="M100 30 L100 22 Q100 12 108 12 Q116 12 116 20"
          fill="none"
          stroke={hanger}
          strokeWidth="2.2"
          strokeLinecap="round"
        />
        <path
          d="M100 30 L56 44 L144 44 Z"
          fill="none"
          stroke={hanger}
          strokeWidth="2.2"
          strokeLinejoin="round"
        />
        <path
          d={BODIES[kind]}
          fill={`url(#fabric-${id})`}
          stroke={shade(safe, -0.3)}
          strokeWidth="0.8"
        />
        <path
          d={DETAILS[kind]}
          fill="none"
          stroke={detail}
          strokeWidth="1.1"
          strokeLinecap="round"
          opacity="0.7"
        />
      </g>
    </svg>
  );
}
