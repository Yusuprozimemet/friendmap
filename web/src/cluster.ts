/**
 * Screen-space clustering for the map.
 *
 * Coordinates arrive as percentages of the 460x552 artwork, and the gazetteer
 * gives every person in a city the *identical* pair — 90 Amsterdammers are 90
 * divs on one pixel. Clustering is what turns that pile back into something
 * countable, and re-running it per zoom level is what lets it come apart again.
 */
import { locationText } from "./format";
import type { Person } from "./types";

export interface Cluster {
  /** Stable across re-renders at the same zoom: the dominant site's key. */
  id: string;
  /** Weighted centroid, in the same percentage space as Person.x / Person.y. */
  x: number;
  y: number;
  people: Person[];
  /** True when every member shares one coordinate — zooming can never split it. */
  exact: boolean;
  /** Most common place among members, e.g. "Amsterdam". */
  label: string;
  /** How many distinct places are folded into this cluster. */
  places: number;
  /** Share of members who posted within the last 7 days, 0..1. */
  freshShare: number;
  /** The offshore "no location given" marker — styled apart from real places. */
  unknown: boolean;
}

interface Site {
  key: string;
  x: number;
  y: number;
  people: Person[];
}

/** Points closer than this on screen are merged. Roughly a fingertip. */
export const CLUSTER_RADIUS_PX = 26;

/** Above this, a fan-out would be a hairball — the list panel takes over. */
export const SPIDER_MAX = 20;

/**
 * People who never named a place arrive pinned to Amsterdam so they show up on
 * the map at all. Left there they *outnumber* the real Amsterdammers 158 to 55
 * on one pixel, which makes the map's biggest marker a place that isn't one.
 * They get their own anchor out in the North Sea instead: still browsable,
 * still one click away, but no longer masquerading as a city.
 */
export const UNKNOWN_XY: readonly [number, number] = [11, 25];

export function isUnknownPlace(p: Person): boolean {
  return p.precision === "none" || p.precision === "country";
}

/** Where a person actually sits on the map, unknowns relocated. */
export function mapXY(p: Person): readonly [number, number] | null {
  if (p.x === null || p.y === null) return null;
  return isUnknownPlace(p) ? UNKNOWN_XY : [p.x, p.y];
}

function siteKey(x: number, y: number): string {
  return `${x.toFixed(3)},${y.toFixed(3)}`;
}

/**
 * Two passes: collapse exact duplicates into sites, then greedily merge sites
 * that fall within `radiusPx` of each other on screen. Seeding by descending
 * size means a cluster centres on its biggest city rather than on whichever
 * hamlet happened to be first in the array.
 */
export function clusterPeople(
  people: Person[],
  opts: { widthPx: number; heightPx: number; zoom: number; radiusPx?: number },
): Cluster[] {
  const { widthPx, heightPx, zoom, radiusPx = CLUSTER_RADIUS_PX } = opts;

  const sites = new Map<string, Site>();
  for (const p of people) {
    const at = mapXY(p);
    if (!at) continue;
    const [x, y] = at;
    const key = siteKey(x, y);
    const site = sites.get(key);
    if (site) site.people.push(p);
    else sites.set(key, { key, x, y, people: [p] });
  }

  const ordered = [...sites.values()].sort(
    (a, b) => b.people.length - a.people.length || a.key.localeCompare(b.key),
  );

  // Percent -> screen pixels. x and y scale differently because the artwork
  // isn't square, and both grow with zoom, which is what splits clusters apart.
  const sx = (widthPx * zoom) / 100;
  const sy = (heightPx * zoom) / 100;
  const r2 = radiusPx * radiusPx;

  const taken = new Array(ordered.length).fill(false);
  const out: Cluster[] = [];

  for (let i = 0; i < ordered.length; i++) {
    if (taken[i]) continue;
    taken[i] = true;
    const seed = ordered[i];
    const members: Site[] = [seed];

    for (let j = i + 1; j < ordered.length; j++) {
      if (taken[j]) continue;
      const dx = (ordered[j].x - seed.x) * sx;
      const dy = (ordered[j].y - seed.y) * sy;
      if (dx * dx + dy * dy <= r2) {
        taken[j] = true;
        members.push(ordered[j]);
      }
    }

    const all = members.flatMap((m) => m.people);
    let wx = 0;
    let wy = 0;
    for (const m of members) {
      wx += m.x * m.people.length;
      wy += m.y * m.people.length;
    }

    const unknown = all.every(isUnknownPlace);
    const { label, places } = describe(all);
    out.push({
      id: seed.key,
      x: wx / all.length,
      y: wy / all.length,
      people: all,
      exact: members.length === 1,
      label: unknown ? "no location given" : label,
      places: unknown ? 1 : places,
      freshShare: all.filter((p) => p.days_ago <= 7).length / all.length,
      unknown,
    });
  }

  return out;
}

function describe(people: Person[]): { label: string; places: number } {
  const counts = new Map<string, number>();
  for (const p of people) {
    const t = locationText(p);
    counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  let label = "";
  let best = -1;
  for (const [name, n] of counts) {
    if (n > best) {
      best = n;
      label = name;
    }
  }
  return { label, places: counts.size };
}

/**
 * Leaflet's spiral, in screen pixels relative to the cluster centre. A ring is
 * tidier for small groups; past ~9 legs a ring either overlaps or gets so wide
 * it covers half the country, so it unwinds into a spiral instead.
 */
export function spiderPositions(count: number): Array<{ dx: number; dy: number }> {
  if (count <= 9) {
    const radius = Math.max(34, (count * 26) / (2 * Math.PI));
    return Array.from({ length: count }, (_, i) => {
      const angle = (2 * Math.PI * i) / count - Math.PI / 2;
      return { dx: radius * Math.cos(angle), dy: radius * Math.sin(angle) };
    });
  }

  const separation = 28;
  const lengthFactor = 5;
  let legLength = 13;
  let angle = 0;
  const out: Array<{ dx: number; dy: number }> = new Array(count);
  for (let i = count - 1; i >= 0; i--) {
    angle += separation / legLength + i * 0.0005;
    out[i] = {
      dx: legLength * Math.cos(angle),
      dy: legLength * Math.sin(angle),
    };
    legLength += (2 * Math.PI * lengthFactor) / angle;
  }
  return out;
}
