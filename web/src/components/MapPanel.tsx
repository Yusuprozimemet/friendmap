import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { C, bucketOf, dotColors, haloGradient } from "../theme";
import { headline, locationText } from "../format";
import { NL_PATH } from "../nlMapPath";
import { SPIDER_MAX, clusterPeople, mapXY, spiderPositions } from "../cluster";
import type { Cluster } from "../cluster";
import type { Person } from "../types";
import { PROVINCE_XY, PROVINCES } from "../types";

interface Props {
  placed: Person[];
  unplacedCount: number;
  selectedId: string | null;
  hoveredId: string | null;
  /** Members of the cluster currently open in the side panel, if any. */
  clusterIds: Set<string> | null;
  provinceLayerOn: boolean;
  unplacedOpen: boolean;
  onSelect: (id: string) => void;
  onSelectCluster: (c: Cluster) => void;
  onHover: (id: string | null) => void;
  onToggleProvinceLayer: () => void;
  onToggleUnplaced: () => void;
  onResetView: () => void;
}

const LEGEND_ROW: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 6,
  marginBottom: 4,
};

const MIN_ZOOM = 1;
const MAX_ZOOM = 14;
/** Breathing room so the coastline never sits flush against the viewport. */
const MAP_INSET = 16;

interface View {
  z: number;
  x: number;
  y: number;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

export function MapPanel({
  placed,
  unplacedCount,
  selectedId,
  hoveredId,
  clusterIds,
  provinceLayerOn,
  unplacedOpen,
  onSelect,
  onSelectCluster,
  onHover,
  onToggleProvinceLayer,
  onToggleUnplaced,
  onResetView,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [avail, setAvail] = useState({ w: 0, h: 0 });
  const [view, setView] = useState<View>({ z: 1, x: 0, y: 0 });
  const [hoveredCluster, setHoveredCluster] = useState<string | null>(null);
  const [legendOpen, setLegendOpen] = useState(true);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setAvail({ w: width, h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // The viewport is the whole panel; the artwork is fitted inside it. Sizing
  // the viewport *as* the artwork is what left a landscape panel showing a
  // narrow portrait column with nothing to pan into once you zoomed.
  const vw = Math.max(1, avail.w);
  const vh = Math.max(1, avail.h);
  /**
   * Artwork size at 1x: the largest that still shows the whole country, less
   * a margin. The silhouette's bounding box is the full 460x552 viewBox —
   * Limburg's tip is literally on the last pixel — so a perfect fit puts the
   * coastline flush against the edges and reads as clipped even though
   * nothing is missing.
   */
  const inset = Math.min(MAP_INSET, vw * 0.06, vh * 0.06);
  const cw = Math.max(
    200,
    Math.min(vw - inset * 2, ((vh - inset * 2) * 460) / 552),
  );
  const ch = (cw * 552) / 460;

  // Pan/zoom maths needs these inside event handlers that shouldn't re-bind
  // on every resize.
  const sizeRef = useRef({ vw, vh, cw, ch });
  sizeRef.current = { vw, vh, cw, ch };

  /**
   * Keeps the artwork inside the viewport: centred on any axis where it's
   * smaller than the viewport, otherwise clamped so no edge pulls inward.
   */
  const clampView = useCallback((v: View): View => {
    const { vw, vh, cw, ch } = sizeRef.current;
    const dw = cw * v.z;
    const dh = ch * v.z;
    return {
      z: v.z,
      x: dw <= vw ? (vw - dw) / 2 : clamp(v.x, vw - dw, 0),
      y: dh <= vh ? (vh - dh) / 2 : clamp(v.y, vh - dh, 0),
    };
  }, []);

  // Start the legend folded when the map is too short to spare the room.
  const legendSized = useRef(false);
  useEffect(() => {
    if (legendSized.current || avail.h <= 0) return;
    legendSized.current = true;
    if (avail.h < 520) setLegendOpen(false);
  }, [avail.h]);

  // A shrinking box can leave the pan out of bounds — pull it back in.
  useEffect(() => {
    setView((v) => clampView(v));
  }, [avail.w, avail.h, clampView]);

  /** Zoom about a point in box-local pixels, so the cursor stays put. */
  const zoomAt = useCallback(
    (factor: number, ax: number, ay: number) => {
      setView((v) => {
        const z = clamp(v.z * factor, MIN_ZOOM, MAX_ZOOM);
        const k = z / v.z;
        return clampView({ z, x: ax - (ax - v.x) * k, y: ay - (ay - v.y) * k });
      });
    },
    [clampView],
  );

  // Wheel has to be non-passive to preventDefault, which React's onWheel can't do.
  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      zoomAt(
        Math.exp(-e.deltaY * 0.0015),
        e.clientX - rect.left,
        e.clientY - rect.top,
      );
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  // A drag that ends on a dot must not also select it.
  const drag = useRef({ active: false, x: 0, y: 0, moved: false });
  const [grabbing, setGrabbing] = useState(false);

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    drag.current = { active: true, x: e.clientX, y: e.clientY, moved: false };
    setGrabbing(true);
  };

  // Deliberately not setPointerCapture: Chrome retargets the compatibility
  // click to the capturing element, which would swallow every dot click.
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (!drag.current.active) return;
      const dx = e.clientX - drag.current.x;
      const dy = e.clientY - drag.current.y;
      if (!drag.current.moved && Math.abs(dx) + Math.abs(dy) > 4)
        drag.current.moved = true;
      drag.current.x = e.clientX;
      drag.current.y = e.clientY;
      setView((v) => clampView({ ...v, x: v.x + dx, y: v.y + dy }));
    };
    const onUp = () => {
      if (!drag.current.active) return;
      drag.current.active = false;
      setGrabbing(false);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [clampView]);

  const resetView = () => {
    setView(clampView({ z: 1, x: 0, y: 0 }));
    onResetView();
  };

  /** Centre a cluster and zoom in — the way to break a mixed cluster apart. */
  const zoomToCluster = (c: Cluster) => {
    const s = sizeRef.current;
    setView((v) => {
      const z = clamp(v.z * 2.2, MIN_ZOOM, MAX_ZOOM);
      return clampView({
        z,
        x: s.vw / 2 - (c.x / 100) * s.cw * z,
        y: s.vh / 2 - (c.y / 100) * s.ch * z,
      });
    });
  };

  const clusters = useMemo(
    () => clusterPeople(placed, { widthPx: cw, heightPx: ch, zoom: view.z }),
    [placed, cw, ch, view.z],
  );

  const maxCount = Math.max(1, ...clusters.map((c) => c.people.length));

  // Province blob radii use a sqrt scale — linear over-weights the busy provinces.
  const provinceCounts: Record<string, number> = {};
  for (const p of placed) {
    if (p.province) provinceCounts[p.province] = (provinceCounts[p.province] ?? 0) + 1;
  }
  const maxProvCount = Math.max(1, ...Object.values(provinceCounts));

  const dimOthers = clusterIds !== null || selectedId !== null;
  /** Screen px -> viewBox units, for leader lines that stay 1px at any zoom. */
  const vbPerPx = 460 / (cw * view.z);

  const isActive = (c: Cluster) =>
    (clusterIds !== null && c.people.some((p) => clusterIds.has(p.id))) ||
    (selectedId !== null && c.people.some((p) => p.id === selectedId));

  /** Single dot, used both standalone and as a spider leg endpoint. */
  const personDot = (p: Person, opts: { dx?: number; dy?: number } = {}) => {
    const at = mapXY(p);
    if (!at) return null;
    const isSel = selectedId === p.id;
    const isHov = hoveredId === p.id;
    const bucket = bucketOf(p.days_ago);
    const isCity = p.precision === "city";
    const dc = dotColors(bucket);
    const spider = opts.dx !== undefined;
    // Legs are already pulled clear of each other, so they don't need the
    // oversized "approximate" halo to stay hittable.
    const base = isCity || spider ? 14 : 34;
    const dim = isSel ? base * 1.4 : base;

    return (
      <div
        key={p.id}
        role="button"
        tabIndex={-1}
        title={`${headline(p)} — ${locationText(p)}`}
        onClick={(e) => {
          if (drag.current.moved) return;
          e.stopPropagation();
          onSelect(p.id);
        }}
        onMouseEnter={() => onHover(p.id)}
        onMouseLeave={() => onHover(null)}
        style={{
          position: "absolute",
          left: `${at[0]}%`,
          top: `${at[1]}%`,
          width: dim,
          height: dim,
          borderRadius: "50%",
          // scale(1/z) cancels the wrapper's zoom so dots keep their pixel size;
          // the trailing translate is therefore in real screen pixels.
          transform: `translate(-50%,-50%) scale(${(isSel ? 1.15 : 1) / view.z}) translate(${
            (opts.dx ?? 0) / (isSel ? 1.15 : 1)
          }px, ${(opts.dy ?? 0) / (isSel ? 1.15 : 1)}px)`,
          cursor: "pointer",
          transition: "width 150ms, height 150ms",
          // City pins read as precise; province pins are deliberately
          // soft so "approximate" is legible without the legend.
          background: isCity || spider ? dc.bg : haloGradient(bucket),
          border: isCity || spider ? dc.border : "none",
          boxShadow:
            isCity || spider
              ? isSel || isHov
                ? "0 3px 10px rgba(0,0,0,0.25)"
                : "0 1px 3px rgba(0,0,0,0.15)"
              : "none",
          opacity: dimOthers && !isSel && !spider && isCity ? 0.4 : 1,
          zIndex: isSel ? 6 : isHov ? 5 : 2,
        }}
      />
    );
  };

  return (
    <div
      style={{
        flex: 1,
        position: "relative",
        background: C.mapBg,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        minWidth: 0,
      }}
    >
      {/* Controls live outside the map box on purpose: inside it they covered
          Groningen, and they shared a container with the drag handler. */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 16px",
          borderBottom: `1px solid ${C.border}`,
          background: C.panel,
          flexShrink: 0,
        }}
      >
        <div style={{ fontSize: 11.5, color: C.muted }}>
          {view.z > 1.02
            ? `${view.z.toFixed(1)}× — drag to pan`
            : "Scroll to zoom · click a group to list it"}
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button
            onClick={onToggleProvinceLayer}
            style={{
              height: 30,
              borderRadius: 8,
              border: `1px solid ${provinceLayerOn ? C.accent : C.border}`,
              background: provinceLayerOn ? C.accent : C.panel,
              color: provinceLayerOn ? "#fff" : C.body,
              fontSize: 11.5,
              fontWeight: 600,
              cursor: "pointer",
              padding: "0 12px",
              whiteSpace: "nowrap",
              fontFamily: "inherit",
            }}
          >
            Provinces
          </button>
          <button
            onClick={() => zoomAt(1.6, vw / 2, vh / 2)}
            title="Zoom in"
            style={ZOOM_BTN}
          >
            +
          </button>
          <button
            onClick={() => zoomAt(1 / 1.6, vw / 2, vh / 2)}
            title="Zoom out"
            style={ZOOM_BTN}
          >
            −
          </button>
          {/* Was ⛶, which reads as "fullscreen" — it has always been a reset. */}
          <button
            onClick={resetView}
            title="Back to the whole country, selection cleared"
            style={{ ...ZOOM_BTN, width: "auto", padding: "0 12px", fontSize: 11.5, fontWeight: 600 }}
          >
            Reset
          </button>
        </div>
      </div>

      <div
        ref={wrapRef}
        style={{
          flex: 1,
          position: "relative",
          display: "flex",
          overflow: "hidden",
          minHeight: 0,
        }}
      >
        <div
          ref={boxRef}
          onPointerDown={onPointerDown}
          style={{
            position: "relative",
            width: "100%",
            height: "100%",
            overflow: "hidden",
            touchAction: "none",
            cursor: grabbing ? "grabbing" : "grab",
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: cw,
              height: ch,
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.z})`,
              transformOrigin: "0 0",
            }}
          >
            <svg
              viewBox="0 0 460 552"
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                overflow: "visible",
              }}
            >
              <path d={NL_PATH} fill={C.land} stroke={C.landStroke} strokeWidth={2} />
              {provinceLayerOn &&
                PROVINCES.map((pv) => {
                  const [xPct, yPct] = PROVINCE_XY[pv];
                  const count = provinceCounts[pv] ?? 0;
                  return (
                    <circle
                      key={pv}
                      cx={(xPct / 100) * 460}
                      cy={(yPct / 100) * 552}
                      r={14 + 34 * Math.sqrt(count / maxProvCount)}
                      fill={
                        count > 0
                          ? "rgba(47,125,110,0.22)"
                          : "rgba(180,172,158,0.12)"
                      }
                    />
                  );
                })}

              {/* Spider legs, drawn under the dots they connect. */}
              {clusters.map((c) => {
                const n = c.people.length;
                if (n < 2 || n > SPIDER_MAX || !isActive(c)) return null;
                const cx = (c.x / 100) * 460;
                const cy = (c.y / 100) * 552;
                return spiderPositions(n).map((pos, i) => (
                  <line
                    key={`${c.id}-leg-${i}`}
                    x1={cx}
                    y1={cy}
                    x2={cx + pos.dx * vbPerPx}
                    y2={cy + pos.dy * vbPerPx}
                    stroke={C.landStroke}
                    strokeWidth={1.2 * vbPerPx}
                  />
                ));
              })}
            </svg>

            {clusters.map((c) => {
              const n = c.people.length;
              const active = isActive(c);

              if (n === 1) return personDot(c.people[0]);

              const spidered = active && n <= SPIDER_MAX;
              const legs = spidered ? spiderPositions(n) : null;

              // Area, not diameter, tracks the count — a linear radius would
              // make the Randstad swallow the map.
              const size = Math.round(24 + 34 * Math.sqrt(n / maxCount));
              const fresh = Math.round(c.freshShare * 100);
              const isHov = hoveredCluster === c.id;

              return (
                <div key={c.id}>
                  <div
                    role="button"
                    tabIndex={-1}
                    title={
                      (c.unknown
                        ? `${n} people who didn't say where they live`
                        : `${n} people — ${c.label}`) +
                      (c.places > 1 ? ` and ${c.places - 1} more place${c.places > 2 ? "s" : ""}` : "") +
                      (spidered ? "" : "\nClick to list them all")
                    }
                    onClick={(e) => {
                      if (drag.current.moved) return;
                      e.stopPropagation();
                      onSelectCluster(c);
                    }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      zoomToCluster(c);
                    }}
                    onMouseEnter={() => setHoveredCluster(c.id)}
                    onMouseLeave={() => setHoveredCluster(null)}
                    style={{
                      position: "absolute",
                      left: `${c.x}%`,
                      top: `${c.y}%`,
                      width: size,
                      height: size,
                      borderRadius: "50%",
                      transform: `translate(-50%,-50%) scale(${
                        (active || isHov ? 1.08 : 1) / view.z
                      })`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: "pointer",
                      // The ring is a share-of-recent gauge: the solid arc is
                      // the slice of this group that posted in the last week.
                      background: c.unknown
                        ? C.chipBg
                        : `conic-gradient(${C.accent} 0 ${fresh}%, ${C.staleRing} ${fresh}% 100%)`,
                      border: c.unknown ? `2px dashed ${C.amber}` : undefined,
                      boxShadow: active
                        ? `0 0 0 3px ${C.accentSel}, 0 4px 14px rgba(0,0,0,0.22)`
                        : "0 2px 8px rgba(0,0,0,0.18)",
                      opacity: dimOthers && !active ? 0.35 : 1,
                      transition: "opacity 150ms",
                      zIndex: active ? 4 : 3,
                    }}
                  >
                    <div
                      style={{
                        width: size - 7,
                        height: size - 7,
                        borderRadius: "50%",
                        background: C.panel,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: clamp(size * 0.36, 10, 16),
                        fontWeight: 700,
                        color: c.unknown ? C.amberInk : C.ink,
                        letterSpacing: "-0.02em",
                      }}
                    >
                      {n}
                    </div>
                  </div>

                  {/* The offshore pile needs saying out loud — it's the one
                      marker whose position carries no meaning. */}
                  {c.unknown && (
                    <div
                      style={{
                        position: "absolute",
                        left: `${c.x}%`,
                        top: `${c.y}%`,
                        transform: `translate(-50%,-50%) scale(${1 / view.z}) translate(0, ${
                          size / 2 + 12
                        }px)`,
                        fontSize: 10.5,
                        fontWeight: 600,
                        color: C.amberInk,
                        whiteSpace: "nowrap",
                        pointerEvents: "none",
                        textAlign: "center",
                      }}
                    >
                      no location given
                    </div>
                  )}

                  {legs?.map((pos, i) => personDot(c.people[i], pos))}
                </div>
              );
            })}
          </div>

          <div
            style={{
              position: "absolute",
              left: 10,
              bottom: 10,
              background: "rgba(255,253,250,0.92)",
              border: `1px solid ${C.border}`,
              borderRadius: 10,
              padding: "10px 12px",
              fontSize: 11,
              color: C.body,
              boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
            }}
          >
            {/* Collapsible: on a short window the map shrinks to where six
                legend rows would sit on top of Zeeland. */}
            <button
              onClick={() => setLegendOpen((v) => !v)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                border: "none",
                background: "none",
                padding: 0,
                cursor: "pointer",
                fontWeight: 600,
                marginBottom: legendOpen ? 6 : 0,
                color: C.muted,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                fontSize: 10,
                fontFamily: "inherit",
              }}
            >
              Legend <span style={{ fontSize: 9 }}>{legendOpen ? "▾" : "▸"}</span>
            </button>
            {legendOpen && (
              <>
            <div style={LEGEND_ROW}>
              <span
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  flexShrink: 0,
                  background: `conic-gradient(${C.accent} 0 60%, ${C.staleRing} 60% 100%)`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <span
                  style={{
                    width: 11,
                    height: 11,
                    borderRadius: "50%",
                    background: C.panel,
                  }}
                />
              </span>
              Group — size = how many, arc = share posted this week
            </div>
            <div style={LEGEND_ROW}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: C.accent,
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              Posted this week
            </div>
            <div style={LEGEND_ROW}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: "rgba(47,125,110,0.45)",
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              Posted this month
            </div>
            <div style={LEGEND_ROW}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: "transparent",
                  border: `2px solid ${C.staleRing}`,
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              Older
            </div>
            <div style={LEGEND_ROW}>
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background:
                    "radial-gradient(circle,rgba(47,125,110,0.35),transparent 70%)",
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              Province-level (approx.)
            </div>
            <div style={{ ...LEGEND_ROW, marginBottom: 0 }}>
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: C.chipBg,
                  border: `2px dashed ${C.amber}`,
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              No location given — parked offshore
            </div>
              </>
            )}
          </div>

        </div>
      </div>

      {unplacedCount > 0 && (
        <button
          onClick={onToggleUnplaced}
          style={{
            border: "none",
            borderTop: `1px solid ${C.border}`,
            background: C.amberBg,
            color: C.amberInk,
            padding: "10px 20px",
            fontSize: 12.5,
            fontWeight: 500,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
            textAlign: "left",
            fontFamily: "inherit",
          }}
        >
          <span>⚠</span> {unplacedCount}{" "}
          {unplacedCount === 1 ? "person" : "people"} didn't share a location —
          click to include them below
          <span style={{ marginLeft: "auto" }}>{unplacedOpen ? "▴" : "▾"}</span>
        </button>
      )}
    </div>
  );
}

const ZOOM_BTN: React.CSSProperties = {
  width: 30,
  height: 30,
  borderRadius: 8,
  border: `1px solid ${C.border}`,
  background: C.panel,
  color: C.body,
  fontSize: 17,
  lineHeight: 1,
  cursor: "pointer",
  fontFamily: "inherit",
};
