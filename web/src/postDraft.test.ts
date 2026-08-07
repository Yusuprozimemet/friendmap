import { describe, expect, it } from "vitest";

import { EMPTY_DRAFT, buildBody, buildTitle, checklist } from "./postDraft";
import type { Draft } from "./postDraft";

const draft = (over: Partial<Draft> = {}): Draft => ({ ...EMPTY_DRAFT, ...over });

describe("buildTitle", () => {
  it("combines the tag and the city", () => {
    expect(buildTitle(draft({ age: "27", gender: "M", city: "Delft", lang: "en" }))).toBe(
      "27M in Delft — looking for new friends",
    );
    expect(buildTitle(draft({ age: "27", gender: "M", city: "Delft", lang: "nl" }))).toBe(
      "27M uit Delft — op zoek naar nieuwe vrienden",
    );
  });

  it("falls back to a bare title when nothing is filled in", () => {
    expect(buildTitle(draft({ lang: "en" }))).toBe("Looking for new friends");
    expect(buildTitle(draft({ lang: "nl" }))).toBe("Op zoek naar nieuwe vrienden");
  });

  it("does not leave a dangling joiner when only one field is set", () => {
    expect(buildTitle(draft({ city: "Delft", lang: "en" }))).toBe(
      "Delft — looking for new friends",
    );
    expect(buildTitle(draft({ age: "27", lang: "en" }))).toBe(
      "27 — looking for new friends",
    );
  });

  it("ignores whitespace-only input", () => {
    expect(buildTitle(draft({ age: "  ", city: "  ", lang: "en" }))).toBe(
      "Looking for new friends",
    );
  });
});

describe("buildBody", () => {
  it("never produces the empty-draft artefact", () => {
    // Concatenating an opener with a trailing period used to yield "Hoi!." for
    // a draft nobody had typed into yet.
    expect(buildBody(draft({ lang: "nl" }))).not.toContain("Hoi!.");
    expect(buildBody(draft({ lang: "nl" }))).toMatch(/^Hoi!\n/);
    expect(buildBody(draft({ lang: "en" }))).toMatch(/^Hi!\n/);
  });

  it("writes a grammatical Dutch opener with a city but no age", () => {
    // "woon in Delft" is not a sentence; it needs its own subject.
    expect(buildBody(draft({ city: "Delft", lang: "nl" }))).toContain(
      "Hoi! Ik woon in Delft.",
    );
  });

  it("joins the two Dutch clauses without repeating the subject", () => {
    expect(
      buildBody(draft({ age: "27", gender: "M", city: "Delft", lang: "nl" })),
    ).toContain("Hoi! Ik ben 27M en woon in Delft.");
  });

  it("writes the English opener", () => {
    expect(
      buildBody(draft({ age: "27", gender: "F", city: "Delft", lang: "en" })),
    ).toContain("Hi! I'm 27F and I live in Delft.");
  });

  it("translates the interest slugs for a Dutch post", () => {
    // The vocabulary is English slugs; "coffee en tech" would read as machine
    // output in an otherwise Dutch post.
    const body = buildBody(draft({ interests: ["coffee", "tech"], lang: "nl" }));
    expect(body).toContain("Waar ik van hou: koffie en techniek.");
    expect(body).not.toContain("coffee");
  });

  it("keeps the slugs for an English post", () => {
    expect(buildBody(draft({ interests: ["coffee", "tech"], lang: "en" }))).toContain(
      "Things I'm into: coffee and tech.",
    );
  });

  it("lists three or more interests with commas and a conjunction", () => {
    expect(
      buildBody(draft({ interests: ["coffee", "tech", "hiking"], lang: "en" })),
    ).toContain("coffee, tech and hiking");
  });

  it("does not add a conjunction for a single interest", () => {
    const body = buildBody(draft({ interests: ["coffee"], lang: "en" }));
    expect(body).toContain("Things I'm into: coffee.");
    expect(body).not.toContain(" and ");
  });

  it("passes through an unmapped slug rather than dropping it", () => {
    expect(buildBody(draft({ interests: ["quidditch"], lang: "nl" }))).toContain(
      "quidditch",
    );
  });

  it("omits sections that were left blank", () => {
    const body = buildBody(draft({ lang: "en" }));
    expect(body).not.toContain("Things I'm into");
    expect(body).not.toContain("What I'm looking for");
  });

  it("includes the free-text sections when filled", () => {
    const body = buildBody(
      draft({ about: "I moved here for work.", lookingFor: "a coffee", lang: "en" }),
    );
    expect(body).toContain("I moved here for work.");
    expect(body).toContain("What I'm looking for: a coffee");
  });

  it("always ends with the invitation to message", () => {
    expect(buildBody(draft({ lang: "en" }))).toMatch(/meet up!$/);
    expect(buildBody(draft({ lang: "nl" }))).toMatch(/af te spreken!$/);
  });

  it("never emits three consecutive newlines", () => {
    // Sections are separated by one blank line; an empty section used to leave
    // two, which Reddit renders as a visible gap.
    const bodies = [
      buildBody(draft({ lang: "nl" })),
      buildBody(draft({ age: "27", lang: "en" })),
      buildBody(draft({ interests: ["coffee"], about: "Hi", lookingFor: "chat" })),
    ];
    for (const body of bodies) expect(body).not.toMatch(/\n{3}/);
  });
});

describe("checklist", () => {
  const gaps = { location: 18, age: 22, interests: 30 };

  it("marks items done only when the field has real content", () => {
    const items = checklist(draft(), gaps, 100, 420);
    expect(items.every((i) => !i.done)).toBe(true);

    const filled = checklist(
      draft({
        age: "27",
        city: "Delft",
        interests: ["coffee"],
        lookingFor: "a coffee",
        about: "x".repeat(80),
      }),
      gaps,
      100,
      420,
    );
    expect(filled.every((i) => i.done)).toBe(true);
  });

  it("does not count whitespace as filled in", () => {
    const items = checklist(draft({ age: "   ", city: "  " }), gaps, 100, 420);
    expect(items.find((i) => i.key === "age")!.done).toBe(false);
    expect(items.find((i) => i.key === "city")!.done).toBe(false);
  });

  it("requires a couple of sentences, not one word", () => {
    const short = checklist(draft({ about: "Hi there" }), gaps, 100, 420);
    expect(short.find((i) => i.key === "about")!.done).toBe(false);
    const long = checklist(draft({ about: "x".repeat(80) }), gaps, 100, 420);
    expect(long.find((i) => i.key === "about")!.done).toBe(true);
  });

  it("turns the corpus gaps into percentages", () => {
    const items = checklist(draft(), gaps, 100, 420);
    expect(items.find((i) => i.key === "city")!.stat).toContain("18%");
    expect(items.find((i) => i.key === "age")!.stat).toContain("22%");
    expect(items.find((i) => i.key === "interests")!.stat).toContain("30%");
    expect(items.find((i) => i.key === "about")!.stat).toContain("420");
  });

  it("shows a dash rather than dividing by zero before the first ingest", () => {
    const items = checklist(draft(), {}, 0, 0);
    expect(items.find((i) => i.key === "city")!.stat).toContain("—");
    expect(items.find((i) => i.key === "city")!.stat).not.toContain("NaN");
  });

  it("makes no claim it cannot support for 'what you want'", () => {
    // Nothing stores reply counts, so there is no statistic to quote here.
    const item = checklist(draft(), gaps, 100, 420).find(
      (i) => i.key === "lookingFor",
    )!;
    expect(item.stat).toBeUndefined();
  });
});