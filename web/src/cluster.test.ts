import { describe, expect, it } from "vitest";

import {
  CLUSTER_RADIUS_PX,
  SPIDER_MAX,
  UNKNOWN_XY,
  clusterPeople,
  isUnknownPlace,
  mapXY,
  spiderPositions,
} from "./cluster";
import { person } from "./testing";

const VIEW = { widthPx: 460, heightPx: 552, zoom: 1 };

describe("mapXY", () => {
  it("passes through a real coordinate", () => {
    expect(mapXY(person({ x: 40, y: 44 }))).toEqual([40, 44]);
  });

  it("relocates people with no stated place to the offshore anchor", () => {
    // Left on Amsterdam's pin these outnumbered the real Amsterdammers 158 to
    // 55, making the map's biggest marker a place that isn't one.
    expect(mapXY(person({ precision: "none" }))).toEqual(UNKNOWN_XY);
    expect(mapXY(person({ precision: "country" }))).toEqual(UNKNOWN_XY);
  });

  it("returns null when there is no coordinate at all", () => {
    expect(mapXY(person({ x: null, y: 44 }))).toBeNull();
    expect(mapXY(person({ x: 40, y: null }))).toBeNull();
  });
});

describe("isUnknownPlace", () => {
  it("covers exactly the two imprecise precisions", () => {
    expect(isUnknownPlace(person({ precision: "none" }))).toBe(true);
    expect(isUnknownPlace(person({ precision: "country" }))).toBe(true);
    expect(isUnknownPlace(person({ precision: "province" }))).toBe(false);
    expect(isUnknownPlace(person({ precision: "city" }))).toBe(false);
  });
});

describe("clusterPeople", () => {
  it("collapses everyone on one coordinate into a single exact cluster", () => {
    const people = Array.from({ length: 5 }, (_, i) =>
      person({ id: `p${i}`, x: 40, y: 44 }),
    );
    const clusters = clusterPeople(people, VIEW);
    expect(clusters).toHaveLength(1);
    expect(clusters[0].people).toHaveLength(5);
    expect(clusters[0].exact).toBe(true);
  });

  it("skips people with no coordinate instead of clustering them at 0,0", () => {
    const clusters = clusterPeople(
      [person({ id: "a", x: 40, y: 44 }), person({ id: "b", x: null, y: null })],
      VIEW,
    );
    expect(clusters).toHaveLength(1);
    expect(clusters[0].people.map((p) => p.id)).toEqual(["a"]);
  });

  it("returns nothing for an empty board", () => {
    expect(clusterPeople([], VIEW)).toEqual([]);
  });

  it("merges points within the radius and splits them as zoom rises", () => {
    // ~1% apart on x is about 4.6px at zoom 1 — inside the radius. At zoom 20
    // it is 92px, well outside.
    const people = [
      person({ id: "a", x: 40, y: 44, city: "Amsterdam" }),
      person({ id: "b", x: 41, y: 44, city: "Haarlem" }),
    ];
    expect(clusterPeople(people, VIEW)).toHaveLength(1);
    expect(clusterPeople(people, { ...VIEW, zoom: 20 })).toHaveLength(2);
  });

  it("marks a merged cluster inexact so the UI offers a fan-out", () => {
    const people = [
      person({ id: "a", x: 40, y: 44 }),
      person({ id: "b", x: 40.2, y: 44 }),
    ];
    const [cluster] = clusterPeople(people, VIEW);
    expect(cluster.exact).toBe(false);
  });

  it("centres a cluster on its biggest site, not on array order", () => {
    // One person in Haarlem listed first, five in Amsterdam after. Seeding by
    // size is what keeps the marker on the city people recognise.
    const people = [
      person({ id: "h", x: 41, y: 44, city: "Haarlem" }),
      ...Array.from({ length: 5 }, (_, i) =>
        person({ id: `a${i}`, x: 40, y: 44, city: "Amsterdam" }),
      ),
    ];
    const [cluster] = clusterPeople(people, VIEW);
    expect(cluster.label).toBe("Amsterdam");
    // Weighted centroid sits nearer the larger site.
    expect(cluster.x).toBeLessThan(40.5);
  });

  it("counts the distinct places folded in", () => {
    const people = [
      person({ id: "a", x: 40, y: 44, city: "Amsterdam" }),
      person({ id: "b", x: 40.1, y: 44, city: "Haarlem" }),
      person({ id: "c", x: 40.2, y: 44, city: "Haarlem" }),
    ];
    const [cluster] = clusterPeople(people, VIEW);
    expect(cluster.places).toBe(2);
    expect(cluster.label).toBe("Haarlem"); // the most common, not the biggest site
  });

  it("labels the offshore cluster as having no location", () => {
    const people = Array.from({ length: 3 }, (_, i) =>
      person({ id: `u${i}`, precision: "none", city: "Amsterdam" }),
    );
    const [cluster] = clusterPeople(people, VIEW);
    expect(cluster.unknown).toBe(true);
    expect(cluster.label).toBe("no location given");
    // One conceptual place, however many cities' coordinates they borrowed.
    expect(cluster.places).toBe(1);
    expect([cluster.x, cluster.y]).toEqual([UNKNOWN_XY[0], UNKNOWN_XY[1]]);
  });

  it("does not mark a mixed cluster unknown", () => {
    const people = [
      person({ id: "u", precision: "none" }),
      person({ id: "r", x: UNKNOWN_XY[0], y: UNKNOWN_XY[1], city: "Vlissingen" }),
    ];
    const [cluster] = clusterPeople(people, VIEW);
    expect(cluster.unknown).toBe(false);
  });

  it("reports the share of members who posted this week", () => {
    const people = [
      person({ id: "a", x: 40, y: 44, days_ago: 1 }),
      person({ id: "b", x: 40, y: 44, days_ago: 7 }),
      person({ id: "c", x: 40, y: 44, days_ago: 8 }),
      person({ id: "d", x: 40, y: 44, days_ago: 90 }),
    ];
    expect(clusterPeople(people, VIEW)[0].freshShare).toBe(0.5);
  });

  it("keeps every person exactly once across all clusters", () => {
    const people = Array.from({ length: 40 }, (_, i) =>
      person({ id: `p${i}`, x: 10 + (i % 8) * 9, y: 20 + Math.floor(i / 8) * 12 }),
    );
    const clusters = clusterPeople(people, VIEW);
    const ids = clusters.flatMap((c) => c.people.map((p) => p.id));
    expect(ids).toHaveLength(40);
    expect(new Set(ids).size).toBe(40);
  });

  it("gives a stable id at the same zoom so markers don't remount", () => {
    const people = [person({ id: "a", x: 40, y: 44 })];
    expect(clusterPeople(people, VIEW)[0].id).toBe(
      clusterPeople(people, VIEW)[0].id,
    );
  });

  it("honours an explicit radius", () => {
    const people = [
      person({ id: "a", x: 40, y: 44 }),
      person({ id: "b", x: 45, y: 44 }),
    ];
    expect(clusterPeople(people, { ...VIEW, radiusPx: 1 })).toHaveLength(2);
    expect(clusterPeople(people, { ...VIEW, radiusPx: 200 })).toHaveLength(1);
  });
});

describe("spiderPositions", () => {
  it("returns one offset per person", () => {
    for (const n of [1, 2, 5, 9, 10, SPIDER_MAX]) {
      expect(spiderPositions(n)).toHaveLength(n);
    }
  });

  it("is empty for nobody", () => {
    expect(spiderPositions(0)).toEqual([]);
  });

  it("uses an even ring up to nine", () => {
    for (const n of [3, 6, 9]) {
      const radii = spiderPositions(n).map(({ dx, dy }) => Math.hypot(dx, dy));
      // Every leg the same length is what makes it a ring rather than a spiral.
      for (const r of radii) expect(r).toBeCloseTo(radii[0], 6);
      // The radius floor keeps a two- or three-person fan from stacking on the
      // marker it sprang from.
      expect(radii[0]).toBeGreaterThanOrEqual(34);
    }
  });

  it("grows the ring with the number of legs", () => {
    const radius = (n: number) => {
      const { dx, dy } = spiderPositions(n)[0];
      return Math.hypot(dx, dy);
    };
    // Below the floor the radius is pinned; above it, more people means wider.
    expect(radius(9)).toBeGreaterThan(radius(3));
  });

  it("separates adjacent legs enough to be clickable", () => {
    // Not as much as CLUSTER_RADIUS_PX at every size — the ring trades overlap
    // for staying on screen — but never so little that two legs are one target.
    const ring = spiderPositions(9);
    const gap = Math.hypot(ring[0].dx - ring[1].dx, ring[0].dy - ring[1].dy);
    expect(gap).toBeGreaterThan(CLUSTER_RADIUS_PX * 0.75);
  });

  it("unwinds into a spiral past nine, where a ring would cover the country", () => {
    const spiral = spiderPositions(14);
    const radii = spiral.map(({ dx, dy }) => Math.hypot(dx, dy));
    // Not a constant radius any more.
    expect(Math.max(...radii)).toBeGreaterThan(Math.min(...radii) + 10);
  });

  it("produces finite offsets at every size the UI allows", () => {
    for (let n = 1; n <= SPIDER_MAX; n++) {
      for (const { dx, dy } of spiderPositions(n)) {
        expect(Number.isFinite(dx)).toBe(true);
        expect(Number.isFinite(dy)).toBe(true);
      }
    }
  });
});