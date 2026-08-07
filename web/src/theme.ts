/** Palette and type scale, taken from the approved design. */
export const C = {
  bg: "#FAF6F0",
  panel: "#FFFDFA",
  border: "#E7E0D6",
  divider: "#F1EBE1",

  ink: "#2B2622",
  ink2: "#3A342E",
  body: "#4A443E",
  muted: "#7A7168",
  faint: "#9A9086",
  faint2: "#B0A89C",

  accent: "#2F7D6E",
  accentBg: "#E4F0EC",
  accentInk: "#1F5A4F",
  accentSel: "#EAF4F1",

  chipBg: "#F5F0E6",
  chipBorder: "#DCD3C4",

  amber: "#B8752E",
  amberInk: "#8A5A22",
  amberBg: "#F8E9D6",

  mapBg: "#F3EFE7",
  land: "#E4DDCF",
  landStroke: "#D3CABA",
  staleRing: "#C9C2B8",
} as const;

export const FONT =
  "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

/** Recency is the app's primary visual variable — see the legend. */
export type Bucket = "fresh" | "recent" | "stale";

export function bucketOf(daysAgo: number): Bucket {
  if (daysAgo <= 7) return "fresh";
  if (daysAgo <= 30) return "recent";
  return "stale";
}

export function dotColors(bucket: Bucket) {
  if (bucket === "fresh")
    return { bg: C.accent, border: `2px solid ${C.accent}` };
  if (bucket === "recent")
    return {
      bg: "rgba(47,125,110,0.5)",
      border: "2px solid rgba(47,125,110,0.5)",
    };
  return { bg: "transparent", border: `2px solid ${C.staleRing}` };
}

export function haloGradient(bucket: Bucket) {
  const inner =
    bucket === "fresh"
      ? "rgba(47,125,110,0.55)"
      : bucket === "recent"
        ? "rgba(47,125,110,0.32)"
        : "rgba(160,153,140,0.35)";
  return `radial-gradient(circle, ${inner}, transparent 72%)`;
}
