/**
 * Turns the composer form into a post someone can paste into Reddit.
 *
 * The template is the extractor's prompt inverted: the app spends all day
 * failing to find age, location and interests in people's posts, so it knows
 * exactly which facts a good one states plainly.
 */

export interface Draft {
  age: string;
  gender: string;
  city: string;
  interests: string[];
  lookingFor: string;
  about: string;
  lang: "nl" | "en";
}

export const EMPTY_DRAFT: Draft = {
  age: "",
  gender: "",
  city: "",
  interests: [],
  lookingFor: "",
  about: "",
  lang: "nl",
};

/** "27M" / "27F" / "27" — the opener people actually scan for. */
function tag(d: Draft): string {
  return `${d.age.trim()}${d.gender.trim()}`.trim();
}

function joinList(items: string[], lang: "nl" | "en"): string {
  const clean = items.filter(Boolean);
  if (clean.length <= 1) return clean.join("");
  const last = clean[clean.length - 1];
  return `${clean.slice(0, -1).join(", ")} ${lang === "nl" ? "en" : "and"} ${last}`;
}

/** The interest vocabulary is English slugs; a Dutch post shouldn't say
 *  "coffee en tech". */
const INTEREST_NL: Record<string, string> = {
  creative: "creatief bezig zijn",
  gaming: "gamen",
  crafts: "knutselen",
  sports: "sport",
  outdoors: "buiten zijn",
  music: "muziek",
  books: "lezen",
  coffee: "koffie",
  travel: "reizen",
  photography: "fotografie",
  cooking: "koken",
  tech: "techniek",
  fitness: "fitness",
  art: "kunst",
  film: "film",
  pets: "huisdieren",
  hiking: "wandelen",
  boardgames: "bordspellen",
  anime: "anime",
  nightlife: "uitgaan",
  food: "lekker eten",
  cars: "auto's",
  languages: "talen leren",
};

function localiseInterests(slugs: string[], lang: "nl" | "en"): string[] {
  return lang === "nl" ? slugs.map((s) => INTEREST_NL[s] ?? s) : slugs;
}

/**
 * "Hi! I'm 27M and I live in Delft."
 *
 * Built clause by clause rather than by string concatenation with a trailing
 * period, which produced "Hoi!." when someone had filled nothing in yet.
 */
function opener(d: Draft): string {
  const nl = d.lang === "nl";
  const hi = nl ? "Hoi!" : "Hi!";
  const who = tag(d);
  const where = d.city.trim();

  if (!who && !where) return hi;

  const clauses: string[] = [];
  if (who) clauses.push(nl ? `Ik ben ${who}` : `I'm ${who}`);
  if (where) {
    // Without a preceding clause the Dutch needs its own subject:
    // "woon in Delft" is not a sentence, "Ik woon in Delft" is.
    if (nl) clauses.push(who ? `woon in ${where}` : `Ik woon in ${where}`);
    else clauses.push(who ? `I live in ${where}` : `I live in ${where}`);
  }
  return `${hi} ${clauses.join(nl ? " en " : " and ")}.`;
}

export function buildTitle(d: Draft): string {
  const who = tag(d);
  const where = d.city.trim();
  if (d.lang === "nl") {
    const parts = [who, where].filter(Boolean).join(" uit ");
    return parts
      ? `${parts} — op zoek naar nieuwe vrienden`
      : "Op zoek naar nieuwe vrienden";
  }
  const parts = [who, where].filter(Boolean).join(" in ");
  return parts ? `${parts} — looking for new friends` : "Looking for new friends";
}

export function buildBody(d: Draft): string {
  const nl = d.lang === "nl";
  const lines: string[] = [];

  lines.push(opener(d));

  if (d.about.trim()) lines.push("", d.about.trim());

  if (d.interests.length) {
    const list = joinList(localiseInterests(d.interests, d.lang), d.lang);
    lines.push(
      "",
      nl ? `Waar ik van hou: ${list}.` : `Things I'm into: ${list}.`,
    );
  }

  if (d.lookingFor.trim()) {
    lines.push(
      "",
      nl
        ? `Wat ik zoek: ${d.lookingFor.trim()}`
        : `What I'm looking for: ${d.lookingFor.trim()}`,
    );
  }

  lines.push(
    "",
    nl
      ? "Stuur gerust een berichtje als je het leuk lijkt om af te spreken!"
      : "Feel free to send me a message if you'd like to meet up!",
  );

  return lines.join("\n");
}

export interface CheckItem {
  key: "age" | "city" | "interests" | "about" | "lookingFor";
  done: boolean;
  label: string;
  /** Only set where the corpus can actually back the advice. */
  stat?: string;
}

export function checklist(
  d: Draft,
  gaps: Record<string, number>,
  sampleSize: number,
  medianLength: number,
): CheckItem[] {
  const pct = (n: number) =>
    sampleSize ? `${Math.round((100 * n) / sampleSize)}%` : "—";

  return [
    {
      key: "city",
      done: !!d.city.trim(),
      label: "Says where you live",
      stat: `${pct(gaps.location ?? 0)} of posts don't — they can't be found on any map`,
    },
    {
      key: "age",
      done: !!d.age.trim(),
      label: "States your age",
      stat: `${pct(gaps.age ?? 0)} of posts don't`,
    },
    {
      key: "interests",
      done: d.interests.length > 0,
      label: "Names something specific you enjoy",
      stat: `${pct(gaps.interests ?? 0)} of posts give nothing concrete to reply to`,
    },
    {
      key: "lookingFor",
      done: !!d.lookingFor.trim(),
      label: "Says what you actually want (a coffee, a gym buddy, chat)",
    },
    {
      key: "about",
      done: d.about.trim().length >= 80,
      label: "Has a couple of sentences in your own words",
      stat: `the median post here is ${medianLength} characters`,
    },
  ];
}
