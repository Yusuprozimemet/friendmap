import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchAuthConfig,
  fetchInterests,
  fetchMe,
  fetchMyProfile,
  fetchProfiles,
  fetchSources,
  fetchStats,
  filtersToParams,
  logout,
  startGoogleLogin,
  deleteAccount,
} from "./api";
import { AboutView } from "./components/AboutView";
import { AccountMenu } from "./components/AccountMenu";
import { AccountView } from "./components/AccountView";
import { ComposeView } from "./components/ComposeView";
import { DetailPanel } from "./components/DetailPanel";
import { FilterRail } from "./components/FilterRail";
import { InsightsView } from "./components/InsightsView";
import { ListPanel } from "./components/ListPanel";
import { MapPanel } from "./components/MapPanel";
import { C, FONT } from "./theme";
import { usePersonState } from "./usePersonState";
import type { Cluster } from "./cluster";
import type { Filters, Gender, Person } from "./types";
import { DEFAULT_FILTERS } from "./types";

type View = "explore" | "insights" | "compose" | "about" | "account";

/** Debounce so typing in the search box doesn't fire a request per keystroke. */
function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

function isDefault(f: Filters): boolean {
  const d = DEFAULT_FILTERS;
  return (
    f.period === d.period &&
    f.ageMin === d.ageMin &&
    f.ageMax === d.ageMax &&
    (Object.keys(f.genders) as Gender[]).every((g) => f.genders[g]) &&
    f.interests.length === 0 &&
    f.lang.nl &&
    f.lang.en &&
    f.search.trim() === "" &&
    f.provinces.length === 0 &&
    f.sources.length === 0 &&
    f.state === null &&
    !f.includeHidden
  );
}

export default function App() {
  const [view, setView] = useState<View>("explore");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [railOpen, setRailOpen] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  // Ids rather than the Cluster itself: clusters are rebuilt on every zoom
  // change, so holding one would pin a stale snapshot of the map.
  const [clusterSel, setClusterSel] = useState<{
    ids: string[];
    label: string;
    places: number;
  } | null>(null);
  const [unplacedOpen, setUnplacedOpen] = useState(false);
  const [provinceLayerOn, setProvinceLayerOn] = useState(false);

  const debouncedFilters = useDebounced(filters, 250);

  const profilesQuery = useQuery({
    queryKey: ["profiles", filtersToParams(debouncedFilters).toString()],
    queryFn: ({ signal }) => fetchProfiles(debouncedFilters, signal),
    placeholderData: (prev) => prev, // keep the list up while refetching
  });

  const interestsQuery = useQuery({
    queryKey: ["interests"],
    queryFn: ({ signal }) => fetchInterests(signal),
  });

  const sourcesQuery = useQuery({
    queryKey: ["sources"],
    queryFn: ({ signal }) => fetchSources(signal),
  });
  const sources = sourcesQuery.data ?? [];

  const authConfigQuery = useQuery({
    queryKey: ["auth-config"],
    queryFn: ({ signal }) => fetchAuthConfig(signal),
    staleTime: Infinity,
  });
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: ({ signal }) => fetchMe(signal),
    enabled: authConfigQuery.data?.enabled === true,
  });

  const personState = usePersonState(!!meQuery.data);

  // "Best match" needs something to match against, so the option stays
  // disabled until the user has said at least one thing about themselves.
  const myProfileQuery = useQuery({
    queryKey: ["my-profile"],
    queryFn: ({ signal }) => fetchMyProfile(signal),
    enabled: !!meQuery.data,
  });
  const mine = myProfileQuery.data;
  const hasSelfProfile = !!(
    mine &&
    (mine.interests.length > 0 || mine.city || mine.province || mine.age !== null)
  );

  // Falling back rather than erroring keeps Principle 5: signing out, or
  // clearing your profile, degrades to the anonymous view.
  //
  // Gated on the query having actually answered. While it's in flight
  // `hasSelfProfile` is false simply because nothing has loaded yet, and
  // acting on that would yank the user off "Best match" mid-refetch.
  const profileAnswered = !meQuery.data || myProfileQuery.isFetched;
  useEffect(() => {
    if (profileAnswered && filters.sort === "match" && !hasSelfProfile) {
      setFilters((f) => ({ ...f, sort: "newest" }));
    }
  }, [filters.sort, hasSelfProfile, profileAnswered]);

  // The OAuth round trip comes back with ?auth=ok; clear it so a refresh or a
  // shared link doesn't carry a stale sign-in result around.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("auth")) {
      params.delete("auth");
      const qs = params.toString();
      window.history.replaceState(
        null,
        "",
        qs ? `?${qs}` : window.location.pathname,
      );
    }
  }, []);

  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: ({ signal }) => fetchStats(signal),
    enabled: view === "insights",
  });

  // Filter state lives in the URL, so a view is shareable and back/forward work.
  useEffect(() => {
    const qs = filtersToParams(debouncedFilters).toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [debouncedFilters]);

  // Memoised for its *identity*, not its cost: `?? []` built a fresh array on
  // every render, so every useMemo below depending on `people` recomputed on
  // every render and memoised nothing.
  const people = useMemo(
    () => profilesQuery.data?.people ?? [],
    [profilesQuery.data],
  );
  // Everyone carries coordinates now — people who didn't name a place are
  // pinned to Amsterdam and tagged "~ Netherlands" — so the unplaced tray
  // stays empty unless the API ever hands back a person without a position.
  const placed = useMemo(() => people.filter((p) => p.x !== null), [people]);
  const unplaced = useMemo(() => people.filter((p) => p.x === null), [people]);

  const selected: Person | null =
    people.find((p) => p.id === selectedId) ?? null;

  const clusterIdSet = useMemo(
    () => (clusterSel ? new Set(clusterSel.ids) : null),
    [clusterSel],
  );
  // Re-resolved against the live result set, so a filter change narrows the
  // open group instead of showing people who no longer match.
  const clusterMembers = useMemo(
    () => (clusterIdSet ? people.filter((p) => clusterIdSet.has(p.id)) : []),
    [clusterIdSet, people],
  );
  const clusterEmpty = clusterSel !== null && clusterMembers.length === 0;
  useEffect(() => {
    if (clusterEmpty) setClusterSel(null);
  }, [clusterEmpty]);

  const openCluster = (c: Cluster) => {
    setSelectedId(null);
    setClusterSel({
      ids: c.people.map((p) => p.id),
      label: c.label,
      places: c.places,
    });
  };

  const update = (patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setSelectedId(null);
  };
  const reset = () => {
    setFilters(DEFAULT_FILTERS);
    setSelectedId(null);
    setClusterSel(null);
  };

  const hasActiveFilters = !isDefault(filters);

  const activeChips = useMemo(() => {
    const chips: Array<{ label: string; onRemove: () => void }> = [];
    if (filters.period !== DEFAULT_FILTERS.period)
      chips.push({
        label: filters.period === "all" ? "All time" : `${filters.period} days`,
        onRemove: () => update({ period: DEFAULT_FILTERS.period }),
      });
    if (filters.ageMin !== 18 || filters.ageMax !== 70)
      chips.push({
        label: `Age ${filters.ageMin}-${filters.ageMax}`,
        onRemove: () => update({ ageMin: 18, ageMax: 70 }),
      });
    for (const pv of filters.provinces)
      chips.push({
        label: pv,
        onRemove: () =>
          update({ provinces: filters.provinces.filter((x) => x !== pv) }),
      });
    if (filters.state)
      chips.push({
        label:
          filters.state === "saved"
            ? "Saved"
            : filters.state === "contacted"
              ? "Contacted"
              : filters.state === "hidden"
                ? "Not interested"
                : "Unmarked",
        onRemove: () => update({ state: null }),
      });
    for (const s of filters.sources)
      chips.push({
        label: `r/${s}`,
        onRemove: () =>
          update({ sources: filters.sources.filter((x) => x !== s) }),
      });
    for (const i of filters.interests)
      chips.push({
        label: i,
        onRemove: () =>
          update({ interests: filters.interests.filter((x) => x !== i) }),
      });
    if (!filters.lang.nl)
      chips.push({
        label: "English only",
        onRemove: () => update({ lang: { ...filters.lang, nl: true } }),
      });
    if (!filters.lang.en)
      chips.push({
        label: "Dutch only",
        onRemove: () => update({ lang: { ...filters.lang, en: true } }),
      });
    if (filters.search.trim())
      chips.push({
        label: `"${filters.search.trim()}"`,
        onRemove: () => update({ search: "" }),
      });
    return chips;
  }, [filters]);

  // Escape unwinds one level at a time: person, then group, then nothing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setSelectedId((id) => {
        if (id === null) setClusterSel(null);
        return null;
      });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const navBtn = (key: View) => ({
    border: "none",
    borderRadius: 7,
    padding: "7px 13px",
    fontSize: 13.5,
    fontWeight: 600,
    cursor: "pointer",
    fontFamily: "inherit",
    background: view === key ? C.divider : "transparent",
    color: view === key ? C.ink : C.muted,
  });

  const error = profilesQuery.error as Error | undefined;

  return (
    <div
      style={{
        width: "100%",
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: C.bg,
        overflow: "hidden",
        fontFamily: FONT,
      }}
    >
      <div
        style={{
          height: 56,
          minHeight: 56,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
          background: C.panel,
          borderBottom: `1px solid ${C.border}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          <div
            style={{
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: "-0.01em",
              color: C.ink,
            }}
          >
            FriendMap <span style={{ color: C.accent }}>NL</span>
          </div>
          <div style={{ display: "flex", gap: 4 }}>
            <button onClick={() => setView("explore")} style={navBtn("explore")}>
              Explore
            </button>
            <button onClick={() => setView("insights")} style={navBtn("insights")}>
              Insights
            </button>
            <button onClick={() => setView("compose")} style={navBtn("compose")}>
              Write a post
            </button>
            <button onClick={() => setView("about")} style={navBtn("about")}>
              About
            </button>
          </div>
        </div>
        <AccountMenu
          user={meQuery.data ?? null}
          enabled={authConfigQuery.data?.enabled ?? false}
          onSignIn={startGoogleLogin}
          onOpenAccount={() => setView("account")}
          onSignOut={async () => {
            await logout();
            meQuery.refetch();
          }}
        />
      </div>

      {view === "explore" && (
        <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>
          <FilterRail
            filters={filters}
            onChange={update}
            onReset={reset}
            interestCounts={interestsQuery.data ?? []}
            sourceCounts={sources}
            state={personState}
            activeLabels={activeChips.map((c) => c.label)}
            onSignIn={startGoogleLogin}
            hasActiveFilters={hasActiveFilters}
            open={railOpen}
            onToggle={() => setRailOpen((v) => !v)}
          />
          {!railOpen && (
            <button
              onClick={() => setRailOpen(true)}
              aria-label="Show filters"
              style={{
                width: 20,
                border: "none",
                borderRight: `1px solid ${C.border}`,
                background: C.panel,
                color: C.faint2,
                cursor: "pointer",
                fontSize: 14,
              }}
            >
              ▸
            </button>
          )}

          <MapPanel
            placed={placed}
            unplacedCount={unplaced.length}
            selectedId={selectedId}
            hoveredId={hoveredId}
            clusterIds={clusterIdSet}
            provinceLayerOn={provinceLayerOn}
            unplacedOpen={unplacedOpen}
            onSelect={setSelectedId}
            onSelectCluster={openCluster}
            onHover={setHoveredId}
            onToggleProvinceLayer={() => setProvinceLayerOn((v) => !v)}
            onToggleUnplaced={() => setUnplacedOpen((v) => !v)}
            onResetView={() => {
              setSelectedId(null);
              setHoveredId(null);
              setClusterSel(null);
            }}
          />

          <div
            style={{
              width: 380,
              minWidth: 380,
              background: C.panel,
              borderLeft: `1px solid ${C.border}`,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {error && (
              <div
                style={{
                  padding: "12px 20px",
                  background: C.amberBg,
                  color: C.amberInk,
                  fontSize: 12.5,
                }}
              >
                Couldn't reach the API — is the backend running on :8000?
              </div>
            )}
            {selected ? (
              <DetailPanel
                person={selected}
                onBack={() => setSelectedId(null)}
                state={personState}
                onSignIn={startGoogleLogin}
                onAddInterest={(slug) =>
                  setFilters((f) =>
                    f.interests.includes(slug)
                      ? f
                      : { ...f, interests: [...f.interests, slug] },
                  )
                }
              />
            ) : (
              <ListPanel
                placed={clusterSel ? clusterMembers : placed}
                unplaced={clusterSel ? [] : unplaced}
                unplacedOpen={unplacedOpen && !clusterSel}
                selectedId={selectedId}
                hoveredId={hoveredId}
                activeChips={activeChips}
                loading={profilesQuery.isLoading}
                onSelect={setSelectedId}
                onHover={setHoveredId}
                onShowAllTime={() => update({ period: "all" })}
                onReset={reset}
                period={filters.period}
                state={personState}
                onSignIn={startGoogleLogin}
                sort={filters.sort}
                canSortByMatch={hasSelfProfile}
                onSortChange={(sort) => update({ sort })}
                clusterLabel={clusterSel?.label ?? null}
                clusterPlaces={clusterSel?.places ?? 1}
                onClearCluster={() => setClusterSel(null)}
              />
            )}
          </div>
        </div>
      )}

      {view === "insights" && <InsightsView stats={statsQuery.data ?? null} />}
      {view === "account" && meQuery.data && (
        <AccountView
          user={meQuery.data}
          state={personState}
          onSignOut={async () => {
            await logout();
            await meQuery.refetch();
            setView("explore");
          }}
          onDelete={async () => {
            await deleteAccount();
            await meQuery.refetch();
            setView("explore");
          }}
        />
      )}
      {view === "compose" && (
        <ComposeView subreddits={sources.map((s) => s.label)} />
      )}
      {view === "about" && (
        <AboutView subreddits={sources.map((s) => s.label)} />
      )}
    </div>
  );
}
