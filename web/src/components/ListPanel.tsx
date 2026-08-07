import { C, bucketOf, dotColors } from "../theme";
import { headline, relTime } from "../format";
import { SaveButton } from "./SaveButton";
import type { Person } from "../types";
import type { PersonStateApi } from "../usePersonState";

interface ChipDef {
  label: string;
  onRemove: () => void;
}

interface Props {
  placed: Person[];
  unplaced: Person[];
  unplacedOpen: boolean;
  selectedId: string | null;
  hoveredId: string | null;
  activeChips: ChipDef[];
  loading: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
  onShowAllTime: () => void;
  onReset: () => void;
  period: number | "all";
  state: PersonStateApi;
  onSignIn: () => void;
  sort: "newest" | "match";
  canSortByMatch: boolean;
  onSortChange: (sort: "newest" | "match") => void;
  /** Set when the list is scoped to one map group rather than the whole result. */
  clusterLabel?: string | null;
  clusterPlaces?: number;
  onClearCluster?: () => void;
}

function PersonCard({
  p,
  selected,
  hovered,
  onSelect,
  onHover,
  state,
  onSignIn,
}: {
  p: Person;
  selected: boolean;
  hovered: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
  state: PersonStateApi;
  onSignIn: () => void;
}) {
  const dc = dotColors(bucketOf(p.days_ago));
  const mine = state.get(p.person_key);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(p.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(p.id);
        }
      }}
      onMouseEnter={() => onHover(p.id)}
      onMouseLeave={() => onHover(null)}
      style={{
        padding: 12,
        borderRadius: 10,
        cursor: "pointer",
        marginBottom: 6,
        border: `1px solid ${selected ? C.accent : "transparent"}`,
        background: selected ? C.accentSel : hovered ? C.chipBg : "transparent",
        transition: "all 150ms ease-out",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 5,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 7,
            fontSize: 13.5,
            fontWeight: 700,
            color: C.ink,
          }}
        >
          <span
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              flexShrink: 0,
              background: dc.bg,
              border: dc.border,
            }}
          />
          {headline(p)}
          {(p.precision === "none" || p.precision === "country") && (
            <span
              title="Didn't say where — parked offshore on the map"
              style={{
                border: `1px solid ${C.chipBorder}`,
                background: C.amberBg,
                color: C.amberInk,
                borderRadius: 10,
                padding: "1px 6px",
                fontSize: 9.5,
                fontWeight: 700,
                letterSpacing: "0.03em",
              }}
            >
              NL
            </span>
          )}
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            flexShrink: 0,
          }}
        >
          {mine?.status === "contacted" && (
            <span
              title="You marked this person contacted"
              style={{
                fontSize: 9.5,
                fontWeight: 700,
                letterSpacing: "0.03em",
                color: C.accentInk,
                background: C.accentBg,
                borderRadius: 10,
                padding: "1px 6px",
              }}
            >
              SENT
            </span>
          )}
          <div style={{ fontSize: 11.5, color: C.faint, whiteSpace: "nowrap" }}>
            {relTime(p.days_ago)}
          </div>
          <SaveButton
            personKey={p.person_key}
            saved={mine?.saved ?? false}
            signedIn={state.signedIn}
            onToggle={() =>
              state.set(p.person_key, { saved: !(mine?.saved ?? false) })
            }
            onSignIn={onSignIn}
            size={24}
          />
        </div>
      </div>
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: C.ink,
          marginBottom: 3,
          display: "-webkit-box",
          WebkitLineClamp: 1,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {p.title}
      </div>
      <div
        style={{
          fontSize: 12,
          color: C.muted,
          lineHeight: 1.5,
          marginBottom: 7,
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {p.summary}
      </div>
      {p.match_reasons.length > 0 && (
        <div
          style={{
            fontSize: 11,
            color: C.accentInk,
            background: C.accentSel,
            borderRadius: 6,
            padding: "4px 8px",
            marginBottom: 7,
          }}
        >
          {p.match_reasons.join(" · ")}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
        {p.interests.slice(0, 3).map((t) => (
          <span
            key={t}
            style={{
              background: C.chipBg,
              color: "#5A5147",
              borderRadius: 12,
              padding: "2px 8px",
              fontSize: 10.5,
            }}
          >
            {t}
          </span>
        ))}
        <span
          style={{
            marginLeft: "auto",
            fontSize: 10.5,
            color: C.faint2,
            fontWeight: 600,
          }}
        >
          {p.lang === "nl" ? "NL" : "EN"}
        </span>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div style={{ padding: 12, marginBottom: 6 }}>
      <div
        style={{
          height: 12,
          width: "55%",
          background: C.divider,
          borderRadius: 6,
          marginBottom: 8,
        }}
      />
      <div
        style={{
          height: 10,
          width: "80%",
          background: C.divider,
          borderRadius: 6,
          marginBottom: 6,
        }}
      />
      <div
        style={{ height: 10, width: "68%", background: C.divider, borderRadius: 6 }}
      />
    </div>
  );
}

export function ListPanel({
  placed,
  unplaced,
  unplacedOpen,
  selectedId,
  hoveredId,
  activeChips,
  loading,
  onSelect,
  onHover,
  onShowAllTime,
  onReset,
  period,
  state,
  onSignIn,
  sort,
  canSortByMatch,
  onSortChange,
  clusterLabel = null,
  clusterPlaces = 1,
  onClearCluster,
}: Props) {
  const shown = unplacedOpen ? [...placed, ...unplaced] : placed;
  const isEmpty = !loading && shown.length === 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "16px 20px 10px",
          borderBottom: `1px solid ${C.divider}`,
        }}
      >
        {clusterLabel !== null && (
          <button
            onClick={onClearCluster}
            style={{
              border: "none",
              background: "none",
              color: C.muted,
              fontSize: 12.5,
              cursor: "pointer",
              padding: 0,
              marginBottom: 10,
              fontFamily: "inherit",
            }}
          >
            ← All results
          </button>
        )}
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: 10,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 700, color: C.ink }}>
            {placed.length} {placed.length === 1 ? "person" : "people"}
            {clusterLabel !== null && (
              <span style={{ fontWeight: 500, color: C.muted }}>
                {" "}
                in {clusterLabel}
                {clusterPlaces > 1 &&
                  ` +${clusterPlaces - 1} nearby place${clusterPlaces > 2 ? "s" : ""}`}
              </span>
            )}
          </div>
          {/* Option labels stay fixed. A native select sizes itself to its
              widest option, so making one label conditional made the whole
              control resize the moment the profile query resolved. The
              "needs your profile" explanation lives in the tooltip instead. */}
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value as "newest" | "match")}
            title={
              canSortByMatch
                ? "How the list is ordered"
                : "Best match needs your age, city or interests — add them on the account page"
            }
            style={{
              border: "none",
              background: "none",
              color: C.muted,
              fontSize: 12,
              fontFamily: "inherit",
              cursor: "pointer",
              // Belt and braces: pinned so it can't shift even if a label
              // is ever localised to something longer.
              minWidth: 96,
              textAlign: "right",
              textAlignLast: "right",
              padding: 0,
            }}
          >
            <option value="newest">Newest</option>
            <option value="match" disabled={!canSortByMatch}>
              Best match
            </option>
          </select>
        </div>
        {activeChips.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
            {activeChips.map((c) => (
              <button
                key={c.label}
                onClick={c.onRemove}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  border: `1px solid ${C.chipBorder}`,
                  background: C.chipBg,
                  color: C.body,
                  borderRadius: 14,
                  padding: "4px 9px",
                  fontSize: 11.5,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                {c.label} ✕
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "10px 14px" }}>
        {loading && shown.length === 0 && (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        )}

        {placed.map((p) => (
          <PersonCard
            key={p.id}
            p={p}
            selected={selectedId === p.id}
            hovered={hoveredId === p.id}
            onSelect={onSelect}
            onHover={onHover}
            state={state}
            onSignIn={onSignIn}
          />
        ))}

        {unplacedOpen && unplaced.length > 0 && (
          <>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: C.faint2,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                padding: "14px 6px 6px",
              }}
            >
              No location shared
            </div>
            {unplaced.map((p) => (
              <PersonCard
                key={p.id}
                p={p}
                selected={selectedId === p.id}
                hovered={hoveredId === p.id}
                onSelect={onSelect}
                onHover={onHover}
                state={state}
                onSignIn={onSignIn}
              />
            ))}
          </>
        )}

        {isEmpty && (
          <div style={{ padding: "60px 20px", textAlign: "center" }}>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: C.body,
                marginBottom: 6,
              }}
            >
              No one matches these filters.
            </div>
            <div style={{ fontSize: 12.5, color: C.faint, marginBottom: 16 }}>
              Try widening the most likely culprits:
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
                alignItems: "center",
              }}
            >
              {period !== "all" && (
                <button
                  onClick={onShowAllTime}
                  style={{
                    border: `1px solid ${C.chipBorder}`,
                    background: C.chipBg,
                    color: C.body,
                    borderRadius: 20,
                    padding: "6px 14px",
                    fontSize: 12.5,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  Show all time, not just {period}d
                </button>
              )}
              <button
                onClick={onReset}
                style={{
                  border: `1px solid ${C.chipBorder}`,
                  background: C.chipBg,
                  color: C.body,
                  borderRadius: 20,
                  padding: "6px 14px",
                  fontSize: 12.5,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Reset all filters
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
