import type { Person } from "./types";

export function relTime(daysAgo: number): string {
  if (daysAgo <= 0) return "today";
  if (daysAgo < 7) return `${daysAgo}d ago`;
  if (daysAgo < 30) return `${Math.round(daysAgo / 7)}w ago`;
  return `${Math.round(daysAgo / 30)}mo ago`;
}

export function dateStr(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

const GENDER_LETTER: Record<string, string> = {
  M: "M",
  F: "F",
  NB: "NB",
  couple: "Couple",
  unknown: "",
};

/**
 * People who never named a place still carry Amsterdam's coordinates from the
 * API, but the map moves them to a marked offshore anchor rather than letting
 * them bury the real Amsterdammers — see UNKNOWN_XY in cluster.ts. The
 * "~ Netherlands" tag is the same "~" the design uses for province-level
 * approximation.
 */
export function locationText(p: Person): string {
  if (p.precision === "none" || p.precision === "country") return "~ Netherlands";
  if (p.city) return p.city;
  return `~ ${p.province}`;
}

/** True when the pin position is borrowed rather than stated. */
export function isApproximate(p: Person): boolean {
  return p.precision !== "city";
}

/** "27F · Eindhoven" — the line people actually scan. */
export function headline(p: Person): string {
  const letter = GENDER_LETTER[p.gender] ?? "";
  const age = p.age === null ? "" : String(p.age);
  const who = [age, letter].filter(Boolean).join("");
  const loc = locationText(p);
  return who ? `${who} · ${loc}` : loc;
}
