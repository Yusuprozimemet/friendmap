export type Gender = "M" | "F" | "NB" | "couple" | "unknown";
export type Precision = "city" | "province" | "country" | "none";

export type PersonStatus = "contacted" | "hidden";

export interface PersonState {
  person_key: string;
  saved: boolean;
  status: PersonStatus | null;
  note: string;
  updated_at: string;
}

export interface PersonStatePatch {
  saved?: boolean;
  /** `status` is nullable and clearing it is meaningful, so it needs a flag. */
  set_status?: boolean;
  status?: PersonStatus | null;
  note?: string;
}

export interface Person {
  id: string;
  /** Stable across reposts, unlike `id` which is a post id. */
  person_key: string;
  subreddit: string;
  age: number | null;
  gender: Gender;
  city: string | null;
  province: string | null;
  precision: Precision;
  lat: number | null;
  lon: number | null;
  x: number | null;
  y: number | null;
  posted_at: string;
  days_ago: number;
  lang: "nl" | "en";
  title: string;
  body: string;
  summary: string;
  looking_for: string | null;
  interests: string[];
  permalink: string;
  repeat_count: number;
  needs_review: boolean;
  /** Only set when sort=match. */
  match_score: number | null;
  match_reasons: string[];
}

export interface ProfileList {
  total: number;
  placed: number;
  unplaced: number;
  people: Person[];
}

export interface LabelCount {
  label: string;
  count: number;
}

export interface SavedSearch {
  id: number;
  name: string;
  filters: Record<string, unknown>;
  cadence: Cadence;
  last_run_at: string | null;
  last_match_at: string | null;
}

export type Cadence = "daily" | "weekly" | "off";

export interface MyProfile {
  age: number | null;
  city: string | null;
  province: string | null;
  interests: string[];
  age_min: number | null;
  age_max: number | null;
}

export interface WritingTips {
  sample_size: number;
  gaps: LabelCount[];
  median_length: number;
  top_interests: LabelCount[];
}

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  picture: string;
}

export interface Stats {
  active_30d: number;
  new_this_week: number;
  cities_covered: number;
  median_age: number | null;
  posts_per_week: number[];
  top_cities: LabelCount[];
  interest_counts: LabelCount[];
  age_buckets: LabelCount[];
  newest_post_at: string | null;
}

export interface InterestCount {
  slug: string;
  count: number;
}

export type Period = 7 | 30 | 90 | "all";

export interface Filters {
  period: Period;
  ageMin: number;
  ageMax: number;
  genders: Record<Gender, boolean>;
  interests: string[];
  interestMode: "any" | "all";
  lang: { nl: boolean; en: boolean };
  search: string;
  provinces: string[];
  /** Subreddits to include. Empty means every source. */
  sources: string[];
  /** My-list view. Signed in only; null means everyone. */
  state: "saved" | "contacted" | "hidden" | "none" | null;
  /** Hidden people are excluded everywhere unless this is on. */
  includeHidden: boolean;
  /** "match" needs a signed-in user with a profile; falls back to newest. */
  sort: "newest" | "match";
}

export const DEFAULT_FILTERS: Filters = {
  period: 30,
  ageMin: 18,
  ageMax: 70,
  genders: { M: true, F: true, NB: true, couple: true, unknown: true },
  interests: [],
  interestMode: "any",
  lang: { nl: true, en: true },
  search: "",
  provinces: [],
  sources: [],
  state: null,
  includeHidden: false,
  sort: "newest",
};

/** Mirrors the backend's app/models.py INTEREST_VOCAB. */
export const INTEREST_VOCAB = [
  "creative", "gaming", "crafts", "sports", "outdoors", "music", "books",
  "coffee", "travel", "photography", "cooking", "tech", "fitness", "art",
  "film", "pets", "hiking", "boardgames",
  "anime", "nightlife", "food", "cars", "languages",
];

export const PROVINCES = [
  "Noord-Holland",
  "Zuid-Holland",
  "Utrecht",
  "Noord-Brabant",
  "Gelderland",
  "Overijssel",
  "Limburg",
  "Groningen",
  "Friesland",
  "Drenthe",
  "Flevoland",
  "Zeeland",
];

/** Province centroids in the SVG's percentage space, for the choropleth blobs. */
export const PROVINCE_XY: Record<string, [number, number]> = {
  "Noord-Holland": [37.87, 36.43],
  "Zuid-Holland": [30.19, 57.34],
  Utrecht: [46.83, 53.88],
  "Noord-Brabant": [48.11, 72.85],
  Gelderland: [66.02, 55.62],
  Overijssel: [78.80, 41.68],
  Limburg: [66.02, 83.10],
  Groningen: [86.48, 13.45],
  Friesland: [63.46, 18.79],
  Drenthe: [83.91, 27.63],
  Flevoland: [58.35, 39.94],
  Zeeland: [13.57, 76.27],
};
