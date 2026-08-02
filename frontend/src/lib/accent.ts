/**
 * Accent colors.
 *
 * Ported from ryOS (ryokun6/ryos - src/themes/accents.ts) and cut down to what
 * this app actually renders. The idea worth keeping is the derivation: an accent
 * is one base hex, and everything else - the bot's bubble, the focus ring, the
 * send button's gloss - is computed from it rather than hand-picked per color.
 *
 * The bubble is the subtle part. Taking the accent hex directly would give you a
 * fully saturated bubble that fights the text. Instead the accent contributes
 * only its *hue*; saturation and lightness come from a reference swatch, so every
 * accent lands in the same pastel band and the conversation stays readable no
 * matter which one is picked.
 *
 * Vars are written inline on <html>, which beats every stylesheet rule without a
 * specificity fight and needs no rebuild. `blue` writes nothing - the stylesheet
 * defaults already are blue, so the default look stays the single source of truth.
 */

/**
 * `wallpaper` is a live value, not a fixed swatch - the color is sampled from
 * the wallpaper image at startup. ryOS makes it the default, on the reasoning
 * that a fresh install should already look like it belongs to the desktop it
 * sits on rather than shipping an arbitrary blue.
 */
export type AccentId =
  | 'wallpaper'
  | 'blue'
  | 'graphite'
  | 'purple'
  | 'pink'
  | 'red'
  | 'orange'
  | 'green'
  | 'teal';

/** Fixed swatches. `wallpaper` is absent by design - it has no static color. */
const STATIC_ACCENTS: Record<Exclude<AccentId, 'wallpaper'>, string> = {
  blue: '#2765ca',
  graphite: '#888d99',
  purple: '#8344c4',
  pink: '#e0539b',
  red: '#d23b30',
  orange: '#e07b1a',
  green: '#3a9a45',
  teal: '#159aa8',
};

export const ACCENT_ORDER: AccentId[] = [
  'wallpaper',
  'blue',
  'graphite',
  'purple',
  'pink',
  'red',
  'orange',
  'green',
  'teal',
];

export const DEFAULT_ACCENT: AccentId = 'wallpaper';

/** Shown on the wallpaper swatch until a color has actually been sampled. */
export const WALLPAPER_SWATCH_PLACEHOLDER =
  'conic-gradient(from 0deg, #e0539b, #e07b1a, #e8b500, #3a9a45, #159aa8, #2765ca, #8344c4, #e0539b)';

const WALLPAPER_FALLBACK = '#2765ca';

export function isAccentId(v: string | null | undefined): v is AccentId {
  return !!v && (v === 'wallpaper' || v in STATIC_ACCENTS);
}

/** The swatch to paint in the picker for an accent. */
export function accentSwatch(id: AccentId, wallpaperHex: string | null): string {
  if (id === 'wallpaper') return wallpaperHex ?? WALLPAPER_SWATCH_PLACEHOLDER;
  return STATIC_ACCENTS[id];
}

/** The base hex an accent derives from. */
function accentBaseHex(id: AccentId, wallpaperHex: string | null): string {
  if (id === 'wallpaper') return wallpaperHex ?? WALLPAPER_FALLBACK;
  return STATIC_ACCENTS[id];
}

/* --- color math ----------------------------------------------------------- */

interface RGB { r: number; g: number; b: number }

const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)));

function parseHex(hex: string): RGB {
  const c = hex.replace('#', '');
  const v = c.length === 3 ? c.split('').map((x) => x + x).join('') : c;
  return {
    r: parseInt(v.slice(0, 2), 16),
    g: parseInt(v.slice(2, 4), 16),
    b: parseInt(v.slice(4, 6), 16),
  };
}

const mix = (c: RGB, t: RGB, amount: number): RGB => ({
  r: clamp(c.r + (t.r - c.r) * amount),
  g: clamp(c.g + (t.g - c.g) * amount),
  b: clamp(c.b + (t.b - c.b) * amount),
});

const WHITE: RGB = { r: 255, g: 255, b: 255 };
const BLACK: RGB = { r: 0, g: 0, b: 0 };

const lighten = (c: RGB, a: number) => mix(c, WHITE, a);
const darken = (c: RGB, a: number) => mix(c, BLACK, a);

const rgb = ({ r, g, b }: RGB) => `rgb(${r}, ${g}, ${b})`;
const rgba = ({ r, g, b }: RGB, a: number) => `rgba(${r}, ${g}, ${b}, ${a})`;

/** Perceived luminance, 0..1. */
const luminance = ({ r, g, b }: RGB) => (0.299 * r + 0.587 * g + 0.114 * b) / 255;

function rgbToHsl({ r, g, b }: RGB) {
  const rn = r / 255, gn = g / 255, bn = b / 255;
  const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn);
  const delta = max - min;
  const l = (max + min) / 2;
  let h = 0;
  if (delta !== 0) {
    if (max === rn) h = ((gn - bn) / delta) % 6;
    else if (max === gn) h = (bn - rn) / delta + 2;
    else h = (rn - gn) / delta + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  const s = delta === 0 ? 0 : delta / (1 - Math.abs(2 * l - 1));
  return { h, s, l };
}

function hslToRgb(h: number, s: number, l: number): RGB {
  if (s === 0) {
    const v = clamp(l * 255);
    return { r: v, g: v, b: v };
  }
  const hue2rgb = (p: number, q: number, t: number) => {
    let tt = t;
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };
  const hn = h / 360;
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  return {
    r: clamp(hue2rgb(p, q, hn + 1 / 3) * 255),
    g: clamp(hue2rgb(p, q, hn) * 255),
    b: clamp(hue2rgb(p, q, hn - 1 / 3) * 255),
  };
}

/** Stock bot-bubble fills. The accent swaps the hue; S and L stay on these. */
const BOT_BUBBLE_REF = { light: '#bfdbfe', dark: '#353a42' } as const;

function botBubbleBg(base: RGB, isDark: boolean): string {
  const ref = rgbToHsl(parseHex(isDark ? BOT_BUBBLE_REF.dark : BOT_BUBBLE_REF.light));
  const { h, s: accentSat } = rgbToHsl(base);
  // A near-gray accent (graphite) has a meaningless hue - clamp its saturation
  // right down or it picks up a random tint from the rounding.
  const s = accentSat < 0.12 ? Math.min(ref.s, 0.08) : ref.s;
  return rgb(hslToRgb(h, s, ref.l));
}

/**
 * A link/text color with enough contrast against the surface. A raw accent
 * (yellow, say) is illegible on white - nudge it until it clears the midpoint.
 */
function readableOnSurface(base: RGB, isDark: boolean): string {
  let c = base;
  let guard = 0;
  if (isDark) while (luminance(c) < 0.5 && guard++ < 12) c = lighten(c, 0.12);
  else while (luminance(c) > 0.5 && guard++ < 12) c = darken(c, 0.12);
  return rgb(c);
}

/* --- css vars ------------------------------------------------------------- */

export const ACCENT_VAR_NAMES = [
  '--accent',
  '--bubble-bot-bg',
  '--focus-ring',
  '--accent-button-bg',
  '--accent-text',
] as const;

export function accentVars(
  accent: AccentId,
  isDark: boolean,
  wallpaperHex: string | null = null
): Record<string, string> {
  // ryOS's rule: when the wallpaper color isn't available yet, emit *nothing*
  // and let the stylesheet defaults stand. Substituting a placeholder hex would
  // paint every accent surface a color the user never picked - which is exactly
  // how a failed sample turned the whole window blue.
  if (accent === 'wallpaper' && !wallpaperHex) return {};

  const base = parseHex(accentBaseHex(accent, wallpaperHex));

  // Aqua button gloss: dark at the top, the accent through the middle, lighter at
  // the foot. Dark mode drags every stop deep into the darker half of the family
  // so the button sits on the window instead of glowing off it.
  const top = isDark ? darken(base, 0.62) : darken(base, 0.28);
  const mid = isDark ? darken(base, 0.42) : base;
  const bottom = isDark ? darken(base, 0.28) : lighten(base, 0.22);

  return {
    '--accent': rgb(base),
    '--bubble-bot-bg': botBubbleBg(base, isDark),
    '--focus-ring': rgba(base, isDark ? 0.45 : 0.3),
    '--accent-button-bg': `linear-gradient(${rgba(top, 0.78)}, ${rgba(mid, 0.72)}, ${rgba(bottom, 0.78)})`,
    '--accent-text': readableOnSurface(base, isDark),
  };
}

/** Write the accent onto <html>. Inline vars win over every stylesheet rule. */
export function applyAccent(
  accent: AccentId,
  isDark: boolean,
  wallpaperHex: string | null = null
) {
  const root = document.documentElement;
  const vars = accentVars(accent, isDark, wallpaperHex);
  for (const name of ACCENT_VAR_NAMES) {
    const value = vars[name];
    if (value) root.style.setProperty(name, value);
    else root.style.removeProperty(name);
  }
  root.setAttribute('data-accent', accent);
}

/* --- sampling the wallpaper ----------------------------------------------- */

/**
 * Pick the color a wallpaper "is". Straight-averaging an image gives mud, so
 * this follows ryOS: score the candidates and pick a winner, then force the
 * winner into a usable band.
 *
 * The scoring prefers saturated, mid-lightness colors - a wallpaper's character
 * lives in its colorful regions, not in the large dim areas that dominate by
 * pixel count. If nothing is colorful enough, the brightest neutral wins.
 */
const NEUTRAL_SATURATION_MAX = 0.12;

function pickPrimaryColor(palette: RGB[]): RGB | null {
  if (palette.length === 0) return null;

  const scored = palette.map((c) => ({ c, hsl: rgbToHsl(c), lum: luminance(c) }));
  const colorful = scored.filter(({ hsl }) => hsl.s > NEUTRAL_SATURATION_MAX);

  if (colorful.length === 0) {
    return scored.reduce((best, x) => (x.lum > best.lum ? x : best)).c;
  }

  let best = colorful[0].c;
  let bestScore = -1;
  for (const { c, hsl, lum } of colorful) {
    const lumBoost = Math.min(lum / 0.5, 1);
    const lightBoost = 1 - Math.min(Math.abs(hsl.l - 0.62) / 0.62, 1);
    const score = hsl.s * 0.55 + lumBoost * 0.3 + lightBoost * 0.15;
    if (score > bestScore) {
      bestScore = score;
      best = c;
    }
  }
  return best;
}

/**
 * Force a sampled color into a band that works as an accent in both light and
 * dark chrome. A wallpaper can be any lightness at all; an accent can't.
 */
const WALLPAPER_LIGHTNESS = { target: 0.56, min: 0.5, max: 0.6 };
const WALLPAPER_SATURATION = { neutralTint: 0.06, colorfulMin: 0.38, colorfulMax: 0.72 };

function normalizeWallpaperAccent(c: RGB): string {
  const hsl = rgbToHsl(c);
  const { target, min, max } = WALLPAPER_LIGHTNESS;
  const { neutralTint, colorfulMin, colorfulMax } = WALLPAPER_SATURATION;

  if (hsl.s <= NEUTRAL_SATURATION_MAX) {
    const out = hslToRgb(hsl.h, hsl.s <= 0 ? 0 : Math.min(hsl.s, neutralTint), Math.max(target, 0.58));
    return toHex(out);
  }

  const out = hslToRgb(
    hsl.h,
    Math.min(Math.max(hsl.s, colorfulMin), colorfulMax),
    hsl.l >= min && hsl.l <= max ? hsl.l : target
  );
  return toHex(out);
}

function toHex({ r, g, b }: RGB): string {
  return `#${[r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('')}`;
}

/**
 * Sample the accent out of an image. Draws it tiny (the color story survives
 * downsampling; the detail doesn't), buckets pixels into a coarse histogram so
 * near-identical shades count as one candidate, then scores the buckets.
 */
export async function sampleWallpaperAccent(src: string): Promise<string | null> {
  try {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = src;
    await img.decode();

    const w = 64;
    const h = Math.max(1, Math.round((img.naturalHeight / img.naturalWidth) * w));
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, w, h);

    const { data } = ctx.getImageData(0, 0, w, h);
    const buckets = new Map<number, { r: number; g: number; b: number; n: number }>();
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] < 200) continue;
      const r = data[i], g = data[i + 1], b = data[i + 2];
      // 5 bits per channel - enough to separate hues, coarse enough that a
      // gradient doesn't shatter into hundreds of single-pixel candidates.
      const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3);
      const bucket = buckets.get(key);
      if (bucket) {
        bucket.r += r; bucket.g += g; bucket.b += b; bucket.n += 1;
      } else {
        buckets.set(key, { r, g, b, n: 1 });
      }
    }

    const palette = [...buckets.values()]
      .sort((a, b) => b.n - a.n)
      .slice(0, 24)
      .map(({ r, g, b, n }) => ({
        r: clamp(r / n), g: clamp(g / n), b: clamp(b / n),
      }));

    const primary = pickPrimaryColor(palette);
    return primary ? normalizeWallpaperAccent(primary) : null;
  } catch {
    return null; // unsamplable image - caller keeps the fallback
  }
}
