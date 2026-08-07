import { describe, expect, it } from "vitest";

import { headline, isApproximate, locationText, relTime } from "./format";
import { person } from "./testing";

describe("relTime", () => {
  it("reads as today for anything under a day", () => {
    expect(relTime(0)).toBe("today");
    expect(relTime(-1)).toBe("today"); // clock skew must not print "-1d ago"
  });

  it("counts days, then weeks, then months", () => {
    expect(relTime(1)).toBe("1d ago");
    expect(relTime(6)).toBe("6d ago");
    expect(relTime(7)).toBe("1w ago");
    expect(relTime(29)).toBe("4w ago");
    expect(relTime(30)).toBe("1mo ago");
    expect(relTime(365)).toBe("12mo ago");
  });
});

describe("locationText", () => {
  it("names the city when there is one", () => {
    expect(locationText(person({ city: "Delft" }))).toBe("Delft");
  });

  it("marks a province as approximate", () => {
    expect(
      locationText(person({ city: null, province: "Friesland", precision: "province" })),
    ).toBe("~ Friesland");
  });

  it("says ~ Netherlands rather than naming the borrowed pin", () => {
    // The API sends Amsterdam's coordinates for unplaced people so they appear
    // on the map at all. Printing "Amsterdam" here would be a lie the map then
    // repeats in its biggest marker.
    for (const precision of ["none", "country"] as const) {
      expect(locationText(person({ precision, city: "Amsterdam" }))).toBe(
        "~ Netherlands",
      );
    }
  });
});

describe("isApproximate", () => {
  it("is true for everything but a stated city", () => {
    expect(isApproximate(person({ precision: "city" }))).toBe(false);
    expect(isApproximate(person({ precision: "province" }))).toBe(true);
    expect(isApproximate(person({ precision: "country" }))).toBe(true);
    expect(isApproximate(person({ precision: "none" }))).toBe(true);
  });
});

describe("headline", () => {
  it("combines age, gender and place", () => {
    expect(headline(person({ age: 27, gender: "F", city: "Eindhoven" }))).toBe(
      "27F · Eindhoven",
    );
  });

  it("omits an unknown gender rather than printing a placeholder", () => {
    expect(headline(person({ age: 27, gender: "unknown", city: "Delft" }))).toBe(
      "27 · Delft",
    );
  });

  it("spells out couple", () => {
    expect(headline(person({ age: 31, gender: "couple", city: "Delft" }))).toBe(
      "31Couple · Delft",
    );
  });

  it("drops the separator when nothing is known about the person", () => {
    // " · Delft" with a leading separator looked like a rendering bug.
    expect(headline(person({ age: null, gender: "unknown", city: "Delft" }))).toBe(
      "Delft",
    );
  });

  it("handles a gender with no age", () => {
    expect(headline(person({ age: null, gender: "M", city: "Delft" }))).toBe(
      "M · Delft",
    );
  });

  it("never renders undefined for an unexpected gender", () => {
    // The vocabulary is closed server-side, but a new value must degrade to a
    // missing letter rather than the string "undefined".
    const odd = person({ age: 20, city: "Delft" });
    // @ts-expect-error deliberately outside the union
    odd.gender = "X";
    expect(headline(odd)).toBe("20 · Delft");
  });
});