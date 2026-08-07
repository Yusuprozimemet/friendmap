import type { CSSProperties } from "react";
import { C } from "../theme";
import type { Filters, Gender, InterestCount, LabelCount, Period } from "../types";
import type { PersonStateApi } from "../usePersonState";
import { SaveSearchButton } from "./SaveSearchButton";
import { PROVINCES } from "../types";

const PERIODS: Period[] = [7, 30, 90, "all"];

const GENDER_DEFS: Array<{ key: Gender; label: string }> = [
  { key: "M", label: "M" },
  { key: "F", label: "F" },
  { key: "NB", label: "Non-binary" },
  { key: "couple", label: "Couple" },
  { key: "unknown", label: "Not stated" },
];

const sectionLabel: CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: C.body,
  marginBottom: 8,
};

function chipStyle(active: boolean): CSSProperties {
  return {
    border: `1px solid ${active ? C.accent : C.chipBorder}`,
    background: active ? C.accentBg : C.chipBg,
    color: active ? C.accentInk : C.body,
    borderRadius: 14,
    padding: "5px 10px",
    fontSize: 11.5,
    cursor: "pointer",
    fontFamily: "inherit",
    fontWeight: 600,
  };
}

interface Props {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
  onReset: () => void;
  interestCounts: InterestCount[];
  sourceCounts: LabelCount[];
  state: PersonStateApi;
  activeLabels: string[];
  onSignIn: () => void;
  hasActiveFilters: boolean;
  open: boolean;
  onToggle: () => void;
}

export function FilterRail({
  filters: f,
  onChange,
  onReset,
  interestCounts,
  sourceCounts,
  state,
  activeLabels,
  onSignIn,
  hasActiveFilters,
  open,
  onToggle,
}: Props) {
  return (
    <div
      style={{
        width: open ? 280 : 0,
        minWidth: open ? 280 : 0,
        background: C.panel,
        borderRight: open ? `1px solid ${C.border}` : "none",
        overflow: "hidden",
        transition: "width 180ms ease-out",
      }}
    >
      {open && (
        <div style={{ padding: 20, overflowY: "auto", height: "100%" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 18,
            }}
          >
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: C.muted,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
              }}
            >
              Filters
            </div>
            <button
              onClick={onToggle}
              aria-label="Collapse filters"
              style={{
                border: "none",
                background: "none",
                color: C.faint2,
                cursor: "pointer",
                fontSize: 14,
                padding: "2px 6px",
              }}
            >
              ◂
            </button>
          </div>

          <SaveSearchButton
            filters={f}
            activeLabels={activeLabels}
            signedIn={state.signedIn}
            onSignIn={onSignIn}
          />

          {/* Only meaningful once there's a signed-in list to filter by. */}
          {state.signedIn && (
            <div style={{ marginBottom: 22 }}>
              <div style={sectionLabel}>My list</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {(
                  [
                    ["saved", "Saved", state.savedCount],
                    ["contacted", "Contacted", state.contactedCount],
                    ["hidden", "Not interested", state.hiddenCount],
                  ] as const
                ).map(([key, label, count]) => {
                  const active = f.state === key;
                  return (
                    <button
                      key={key}
                      onClick={() =>
                        onChange({ state: active ? null : key })
                      }
                      style={chipStyle(active)}
                    >
                      {label}{" "}
                      <span style={{ fontWeight: 400, opacity: 0.7 }}>{count}</span>
                    </button>
                  );
                })}
              </div>
              {state.hiddenCount > 0 && f.state !== "hidden" && (
                <button
                  onClick={() => onChange({ includeHidden: !f.includeHidden })}
                  style={{
                    marginTop: 8,
                    border: "none",
                    background: "none",
                    padding: 0,
                    color: C.muted,
                    fontSize: 11.5,
                    cursor: "pointer",
                    fontFamily: "inherit",
                    textDecoration: "underline",
                  }}
                >
                  {f.includeHidden ? "Hide" : "Show"} the {state.hiddenCount} I'm
                  not interested in
                </button>
              )}
            </div>
          )}

          {/* Active period — the single most important control, so it leads. */}
          <div style={{ marginBottom: 22 }}>
            <div style={sectionLabel}>Active period</div>
            <div
              style={{
                display: "flex",
                gap: 4,
                background: C.divider,
                borderRadius: 8,
                padding: 3,
              }}
            >
              {PERIODS.map((v) => {
                const active = f.period === v;
                return (
                  <button
                    key={String(v)}
                    onClick={() => onChange({ period: v })}
                    style={{
                      flex: 1,
                      textAlign: "center",
                      border: "none",
                      borderRadius: 6,
                      padding: "7px 0",
                      fontSize: 12.5,
                      fontWeight: 600,
                      cursor: "pointer",
                      fontFamily: "inherit",
                      background: active ? C.panel : "transparent",
                      color: active ? C.ink : "#8A8175",
                      boxShadow: active ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
                    }}
                  >
                    {v === "all" ? "All" : `${v}d`}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Only worth showing once there's more than one place to choose. */}
          {sourceCounts.length > 1 && (
            <div style={{ marginBottom: 22 }}>
              <div style={sectionLabel}>Source</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {sourceCounts.map((s) => {
                  // Empty means "all", so nothing looks switched off by default.
                  const active =
                    f.sources.length === 0 || f.sources.includes(s.label);
                  return (
                    <button
                      key={s.label}
                      onClick={() => {
                        const only = [s.label];
                        const next =
                          f.sources.length === 0
                            ? only
                            : f.sources.includes(s.label)
                              ? f.sources.filter((x) => x !== s.label)
                              : [...f.sources, s.label];
                        // Deselecting everything means all, not none.
                        onChange({
                          sources: next.length === sourceCounts.length ? [] : next,
                        });
                      }}
                      title={`${s.count} posts from r/${s.label}`}
                      style={chipStyle(active)}
                    >
                      r/{s.label}{" "}
                      <span style={{ fontWeight: 400, opacity: 0.7 }}>
                        {s.count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div style={{ marginBottom: 22 }}>
            <div style={sectionLabel}>Province</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {PROVINCES.map((pv) => {
                const active = f.provinces.includes(pv);
                return (
                  <button
                    key={pv}
                    onClick={() =>
                      onChange({
                        provinces: active
                          ? f.provinces.filter((x) => x !== pv)
                          : [...f.provinces, pv],
                      })
                    }
                    style={chipStyle(active)}
                  >
                    {pv}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: 22 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginBottom: 8,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: C.body }}>Age</div>
              <div style={{ fontSize: 12, color: C.muted }}>
                {f.ageMin}–{f.ageMax}
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <input
                type="range"
                min={18}
                max={70}
                value={f.ageMin}
                aria-label="Minimum age"
                onChange={(e) =>
                  onChange({ ageMin: Math.min(Number(e.target.value), f.ageMax) })
                }
                style={{ width: "100%", accentColor: C.accent }}
              />
              <input
                type="range"
                min={18}
                max={70}
                value={f.ageMax}
                aria-label="Maximum age"
                onChange={(e) =>
                  onChange({ ageMax: Math.max(Number(e.target.value), f.ageMin) })
                }
                style={{ width: "100%", accentColor: C.accent }}
              />
            </div>
          </div>

          <div style={{ marginBottom: 22 }}>
            <div style={sectionLabel}>Gender</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {GENDER_DEFS.map((g) => (
                <button
                  key={g.key}
                  onClick={() =>
                    onChange({
                      genders: { ...f.genders, [g.key]: !f.genders[g.key] },
                    })
                  }
                  style={chipStyle(f.genders[g.key])}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 22 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 600, color: C.body }}>
                Interests
              </div>
              {/* With fewer than two interests the modes are the same set —
                  "at least one of {x}" and "all of {x}" are identical — so the
                  toggle looked broken rather than inapplicable. */}
              <button
                disabled={f.interests.length < 2}
                onClick={() =>
                  onChange({
                    interestMode: f.interestMode === "any" ? "all" : "any",
                  })
                }
                title={
                  f.interests.length < 2
                    ? "Pick two or more interests — with one, “any” and “all” mean the same thing"
                    : f.interestMode === "any"
                      ? "Showing people with at least one of these. Click to require all of them."
                      : "Showing only people with every one of these. Click to relax to any."
                }
                style={{
                  border: "none",
                  background: "none",
                  color: f.interests.length < 2 ? C.faint2 : C.accent,
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: f.interests.length < 2 ? "not-allowed" : "pointer",
                  fontFamily: "inherit",
                  padding: 0,
                }}
              >
                {f.interestMode === "any" ? "Match any" : "Match all"}
              </button>
            </div>
            {f.interests.length >= 2 && (
              <div
                style={{
                  fontSize: 11,
                  color: C.muted,
                  marginBottom: 8,
                  lineHeight: 1.5,
                }}
              >
                {f.interestMode === "any"
                  ? `People into ${f.interests.join(" or ")}`
                  : `Only people into ${f.interests.join(" and ")} — most people are tagged with just 1–4 interests, so this narrows hard`}
              </div>
            )}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {interestCounts.map((i) => {
                const active = f.interests.includes(i.slug);
                return (
                  <button
                    key={i.slug}
                    onClick={() =>
                      onChange({
                        interests: active
                          ? f.interests.filter((x) => x !== i.slug)
                          : [...f.interests, i.slug],
                      })
                    }
                    style={chipStyle(active)}
                  >
                    {i.slug} <span style={{ opacity: 0.55 }}>{i.count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: 22 }}>
            <div style={sectionLabel}>Language</div>
            <div style={{ display: "flex", gap: 6 }}>
              {(["nl", "en"] as const).map((code) => {
                const active = f.lang[code];
                return (
                  <button
                    key={code}
                    onClick={() =>
                      onChange({ lang: { ...f.lang, [code]: !active } })
                    }
                    style={{
                      ...chipStyle(active),
                      flex: 1,
                      textAlign: "center",
                      borderRadius: 8,
                      padding: "7px 0",
                      fontSize: 12.5,
                    }}
                  >
                    {code === "nl" ? "Dutch" : "English"}
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ marginBottom: 8 }}>
            <div style={sectionLabel}>Search</div>
            <input
              value={f.search}
              onChange={(e) => onChange({ search: e.target.value })}
              placeholder="title, body, city…"
              style={{
                width: "100%",
                padding: "9px 12px",
                border: `1px solid ${C.border}`,
                borderRadius: 8,
                fontSize: 13,
                background: C.panel,
                color: C.ink,
                fontFamily: "inherit",
              }}
            />
          </div>

          {hasActiveFilters && (
            <button
              onClick={onReset}
              style={{
                marginTop: 10,
                border: "none",
                background: "none",
                color: C.amber,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                padding: 0,
              }}
            >
              Reset all filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
