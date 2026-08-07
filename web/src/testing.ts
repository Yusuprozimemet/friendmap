/**
 * Test-only helper. Kept in src/ so it typechecks with the same tsconfig as
 * the code it builds fixtures for — a fixture that drifts from the `Person`
 * shape is worse than none.
 */
import type { Person, Precision } from "./types";

export function person(over: Partial<Person> = {}): Person {
  return {
    id: "abc123",
    person_key: "k-abc123",
    subreddit: "makenewfriendsNL",
    age: 30,
    gender: "F",
    city: "Amsterdam",
    province: "Noord-Holland",
    precision: "city" as Precision,
    lat: 52.3676,
    lon: 4.9041,
    x: 40.5,
    y: 44.6,
    posted_at: "2026-08-06T10:00:00Z",
    days_ago: 1,
    lang: "en",
    title: "Hi everyone",
    body: "Looking to meet people.",
    summary: "Climbs twice a week.",
    looking_for: null,
    interests: ["hiking"],
    permalink: "https://reddit.com/r/makenewfriendsNL/comments/abc123",
    repeat_count: 0,
    needs_review: false,
    match_score: null,
    match_reasons: [],
    ...over,
  };
}