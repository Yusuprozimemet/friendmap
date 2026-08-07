import type {
  AuthUser,
  Cadence,
  MyProfile,
  SavedSearch,
  WritingTips,
  Filters,
  InterestCount,
  LabelCount,
  PersonState,
  PersonStatePatch,
  ProfileList,
  Stats,
} from "./types";

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  // credentials so the session cookie rides along on /api/auth/me.
  const res = await fetch(path, { signal, credentials: "same-origin" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

/** Filters -> query string. Also what gets mirrored into the address bar. */
export function filtersToParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams();
  if (f.period !== "all") p.set("period", String(f.period));
  else p.set("period", "0");

  p.set("age_min", String(f.ageMin));
  p.set("age_max", String(f.ageMax));

  const genders = (Object.keys(f.genders) as Array<keyof typeof f.genders>)
    .filter((g) => f.genders[g]);
  if (genders.length < 5) p.set("genders", genders.join(","));

  if (f.interests.length) {
    p.set("interests", f.interests.join(","));
    p.set("interest_mode", f.interestMode);
  }

  const langs = [f.lang.nl && "nl", f.lang.en && "en"].filter(Boolean) as string[];
  if (langs.length < 2) p.set("langs", langs.join(","));

  if (f.provinces.length) p.set("provinces", f.provinces.join(","));
  if (f.sources.length) p.set("sources", f.sources.join(","));
  if (f.state) p.set("state", f.state);
  if (f.sort !== "newest") p.set("sort", f.sort);
  if (f.includeHidden) p.set("include_hidden", "true");
  if (f.search.trim()) p.set("search", f.search.trim());

  return p;
}

export function fetchProfiles(f: Filters, signal?: AbortSignal) {
  return get<ProfileList>(`/api/profiles?${filtersToParams(f)}`, signal);
}

export function fetchStats(signal?: AbortSignal) {
  return get<Stats>("/api/stats", signal);
}

export function fetchInterests(signal?: AbortSignal) {
  return get<InterestCount[]>("/api/meta/interests", signal);
}

/** Which subreddits are actually in the data, biggest first. */
export function fetchSources(signal?: AbortSignal) {
  return get<LabelCount[]>("/api/meta/sources", signal);
}

/** The signed-in user, or null when browsing anonymously. */
export function fetchMe(signal?: AbortSignal) {
  return get<AuthUser | null>("/api/auth/me", signal);
}

/** False when the server has no Google credentials — hides the button. */
export function fetchAuthConfig(signal?: AbortSignal) {
  return get<{ enabled: boolean }>("/api/auth/config", signal);
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "same-origin",
  });
}

/** Full-page redirect: the OAuth round trip can't happen inside fetch.
 *  Carries the current view so sign-in returns you where you were. */
export function startGoogleLogin(): void {
  const next = window.location.pathname + window.location.search;
  window.location.href = `/api/auth/google/start?next=${encodeURIComponent(next)}`;
}

export async function deleteAccount(): Promise<void> {
  const res = await fetch("/api/auth/me", {
    method: "DELETE",
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

/** Saved / contacted / hidden / notes, for the signed-in user. */
export function fetchMyPeople(signal?: AbortSignal) {
  return get<PersonState[]>("/api/me/people", signal);
}

export async function setPersonState(
  personKey: string,
  patch: PersonStatePatch,
): Promise<PersonState> {
  const res = await fetch(`/api/me/people/${personKey}`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<PersonState>;
}


// --- saved searches (Spec 3) ---------------------------------------------

export function fetchSearches(signal?: AbortSignal) {
  return get<SavedSearch[]>("/api/me/searches", signal);
}

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    // The 409 "you already have 5" carries a message worth showing verbatim.
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function createSearch(
  name: string,
  filters: Record<string, unknown>,
  cadence: Cadence,
) {
  return send<SavedSearch>("/api/me/searches", "POST", { name, filters, cadence });
}

export function updateSearch(id: number, patch: { name?: string; cadence?: Cadence }) {
  return send<SavedSearch>(`/api/me/searches/${id}`, "PATCH", patch);
}

export function deleteSearch(id: number) {
  return send<{ deleted: boolean }>(`/api/me/searches/${id}`, "DELETE");
}

// --- my profile (Spec 4) -------------------------------------------------

export function fetchMyProfile(signal?: AbortSignal) {
  return get<MyProfile>("/api/me/profile", signal);
}

export function saveMyProfile(profile: MyProfile) {
  return send<MyProfile>("/api/me/profile", "PUT", profile);
}

/** Measured corpus gaps for the post composer (Spec 5). */
export function fetchWritingTips(signal?: AbortSignal) {
  return get<WritingTips>("/api/meta/writing-tips", signal);
}
