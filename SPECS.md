# FriendMap NL — implementation specs

Specs for the account-backed features, in build order. Each is independently
shippable; each states what it needs from the one before it.

| Spec | Status |
| --- | --- |
| 0 — `person_key` | **Done** |
| 1 — Finish sign-in | **Done** |
| 2 — Saved / status / notes | **Done** |
| 3 — Saved searches + alerts | **Done**, live on Resend |
| 4 — Profile + ranking | **Done** |
| 5 — Post composer | **Done** (5b). 5a, the reply-count signal, deliberately not built |

Status at time of writing: 598 people from two subreddits (899 posts), Google
OAuth built but not switched on (`GOOGLE_CLIENT_ID` unset ⇒ `AUTH_ENABLED`
false ⇒ the UI hides the button), nothing gated behind an account.

---

## Principles

Every spec below inherits these. Where a spec contradicts one, it says so and
justifies it.

1. **Browsing never requires an account.** The map, filters and list work
   signed out. An account buys additions, never access.
2. **Reddit stays the messaging layer.** No in-app DMs, no in-app posting. See
   "Explicitly out of scope" at the end for the reasoning.
3. **No new PII about the people on the map.** They didn't sign up. Account
   features attach to the *viewer*, never to the viewed.
4. **Every stored user row must be deletable.** One "delete my account" path
   that really removes everything.
5. **Degrade to anonymous.** If auth is off or a token expires, the app renders
   as the anonymous version rather than erroring.

---

## Spec 0 — Stable person identity `person_key`

**This blocks Specs 2, 3 and 4.** Build it first.

### Problem

There is no `people` table by design — people are grouped by author at query
time. Consequently `Person.id` is a *post* id. When someone posts again,
`dedupe_by_author` surfaces the newer post, and the id changes.

So "save this person" cannot key on `Person.id`: the row silently detaches the
next time they post. Keying on the username would work, but the username was
deliberately removed from the API.

### Solution

Expose a stable, non-reversible identifier derived from the author:

```python
person_key = hmac.new(PERSON_KEY_SECRET, author.lower().encode(), "sha256").hexdigest()[:24]
```

Stable across reposts, constant per person, reveals nothing about the handle,
and cannot be brute-forced back to a username without the secret (a plain
hash could be — the username space is small enough to enumerate).

### Changes

- `config.PERSON_KEY_SECRET` — **durable config**. Rotating it orphans every
  saved row. Document it next to `SESSION_SECRET` and never default it in
  production; refuse to start if auth is on and it's unset.
- `PersonOut.person_key: str` — new serialised field.
- `query.to_person` computes it. Empty author (deleted account) → empty key;
  the UI must not offer "save" on those.
- Frontend `Person.person_key`.

### Acceptance

- Two posts by the same author yield the same `person_key`.
- Different authors never collide across the full dataset (assert in a test).
- `person_key` does not appear in any log line.
- Changing `PERSON_KEY_SECRET` changes every key (proves it's actually keyed).

**Effort:** S — half a day.

---

## Spec 1 — Finish sign-in

OAuth works end to end but has no visible entry point when unconfigured, and
no account-management surface.

### Problem

`AccountMenu` returns `null` when `/api/auth/config` reports `enabled: false`.
Correct for production, confusing in development — it looks broken rather than
switched off.

### Scope

1. **Setup visibility.** When `enabled` is false *and* the app is served from
   localhost, render a muted "Sign-in not configured" chip linking to the
   README section, instead of nothing. In production, keep rendering nothing.
2. **Sign-in prompt in context.** The header button is the only affordance
   today. Add an inline prompt at the point of need — e.g. the save control in
   Spec 2 shows "Sign in to save" for anonymous users rather than hiding.
3. **Account page.** Reachable from the menu: email shown, "Sign out",
   "Delete my account and everything saved" with a typed confirmation. Delete
   removes the user row and cascades to all feature tables.
4. **Post-login return.** Remember where the user was before the redirect and
   return them there, not to `/`. Store the path in the session at `start`,
   validate it's a local path on the way back (never an absolute URL — that's
   an open-redirect).

### Acceptance

- Anonymous → sign in → land back on the same filtered view, filters intact.
- Delete account → row gone, session cleared, app still browsable.
- With `GOOGLE_CLIENT_ID` unset, production build shows no auth UI at all.
- A callback carrying `?next=https://evil.example` is rejected.

**Effort:** S/M — one day.

---

## Spec 2 — Saved people, status and notes

The first reason to have an account. Depends on Spec 0.

### User story

> I found four people worth messaging. I message two, get one reply, and by
> next week I can't remember which. I want to mark who I've contacted, hide
> the ones who aren't a fit, and keep a note.

### Data

```
user_person (
  user_id      FK users(id) ON DELETE CASCADE,
  person_key   varchar(24),
  saved        boolean default false,
  status       varchar(16),      -- null | 'contacted' | 'hidden'
  note         text default '',
  created_at, updated_at         timestamptz,
  PRIMARY KEY (user_id, person_key)
)
```

One row per (user, person). `saved`, `status` and `note` are independent —
you can note someone without saving them.

### API

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/api/me/people` | All rows for the user. Returns keys + state, not profiles. |
| `PUT` | `/api/me/people/{person_key}` | Upsert `{saved, status, note}`. Partial. |
| `DELETE` | `/api/me/people/{person_key}` | Clear the row entirely. |

`GET /api/profiles` gains an optional `state` filter (`saved`, `contacted`,
`hidden`, `none`) — applied **after** dedupe, in Python, alongside the province
filter.

### UI

- Heart/bookmark on each list card and in `DetailPanel`.
- `DetailPanel` gains a status selector (`—` / Contacted / Not interested) and
  a note field, autosaved on blur.
- Filter rail: new "My list" section — *Saved · Contacted · Hidden* chips.
  Hidden people are excluded by default once the user has hidden anyone; a
  "Show hidden (12)" toggle restores them.
- Map: saved people get a distinct marker ring; hidden ones drop out of
  clusters entirely (so counts stay honest).

### Rules and edge cases

- **Anonymous users**: controls visible but inert, with "Sign in to save".
  Don't hide them — they're the main reason to sign up.
- **Deleted posts**: a saved person whose posts are all gone still appears in
  "My list", greyed, labelled "post removed". Don't silently drop it — the
  user may still have an open conversation with them.
- **Person reappears** under a new post: the row follows them automatically,
  which is the whole point of Spec 0.
- Hidden must not be confused with blocked; it's a personal view filter and
  affects nobody else.

### Acceptance

- Save someone, repost happens (simulate by inserting a newer post from the
  same author), saved state still attached.
- Hide 10 people, map cluster counts drop by exactly 10.
- Delete account → all `user_person` rows gone.
- Anonymous save attempt → 401, UI shows the sign-in prompt, nothing written.

**Effort:** M — two to three days.

---

## Spec 3 — Saved searches and email alerts

The strongest feature, and the only one that *requires* an account. Depends on
Specs 0 and 1.

### User story

> The right person for me might post next Tuesday. I'm not going to check this
> site every day, so I'll never see it.

Reddit cannot do this: it has no structured filters over age, city and
interest.

### Blocking decision

**Email transport is unchosen.** Options, cheapest first:

- **Resend / Postmark / SendGrid** — an API key and ~20 lines. Free tiers
  cover thousands/month. Recommended.
- **SMTP via your own domain** — no vendor, but deliverability is a project in
  itself; expect spam-foldering.

Nothing in this spec ships until that's picked. Everything else can be built
and tested against a console-logging sender.

### Data

```
saved_search (
  id, user_id FK users(id) ON DELETE CASCADE,
  name          varchar(80),        -- user-supplied or auto from filters
  filters       jsonb,              -- the same shape as the URL query string
  cadence       varchar(16),        -- 'daily' | 'weekly' | 'off'
  last_run_at   timestamptz,
  last_match_at timestamptz,
  created_at    timestamptz
)

alert_sent (                        -- prevents re-notifying about one person
  saved_search_id FK ON DELETE CASCADE,
  person_key      varchar(24),
  sent_at         timestamptz,
  PRIMARY KEY (saved_search_id, person_key)
)
```

Storing filters as the query-string shape means the "run this search" code is
the *same* code the API already uses — no second implementation to drift.

Cap: **5 saved searches per user**. Prevents someone saving 200 searches and
turning the job into a scraper.

### Job

Runs at the end of `pipeline.run_daily`, after new profiles land:

1. For each active `saved_search` due by cadence:
2. Run the stored filters through the existing query path.
3. Drop anyone already in `alert_sent`, and anyone the user has `hidden`.
4. If matches remain, queue one email; insert the `alert_sent` rows **only
   after the send succeeds**, so a failure retries tomorrow rather than
   silently swallowing the match.
5. Update `last_run_at`.

Send **one digest per user**, not one per search — three saved searches must
not mean three emails.

### Email

- Subject: `3 new people near Rotterdam`.
- Body: name-free. Age, city, one-line summary, link back to the app (not
  straight to Reddit — the app is where the person can be marked contacted).
- **Unsubscribe link in every email**, one click, no login: a signed token
  (`itsdangerous`, same secret pattern as sessions) that sets `cadence='off'`.
  This is a legal requirement, not a nicety.
- Never send an empty digest.

### UI

- "Save this search" button in the filter rail, enabled when any filter is
  active. Prefills a name from the active chips ("25–35 · Rotterdam ·
  boardgames").
- Account page lists saved searches with cadence dropdown, match count since
  last run, and delete.

### Acceptance

- Save a search matching nobody; ingest a matching post; exactly one email
  queued, containing that person.
- Run the job twice with no new data → no second email.
- Send failure → `alert_sent` unwritten → retried next run.
- Unsubscribe token sets cadence off and cannot be replayed to change another
  user's search.
- User with 3 saved searches and matches in all 3 → 1 email.

### Risks

- **Spam perception.** Daily cap, digest-only, obvious unsubscribe.
- **Empty-app problem.** With ~5 new people/week per subreddit, weekly is the
  better default cadence. Make weekly the default, not daily.

**Effort:** L — four to five days, plus the transport decision.

---

## Spec 4 — Your profile and compatibility ranking

Depends on Spec 0. Independent of 2 and 3.

### User story

> I'm 27, in Utrecht, into boardgames and hiking. Stop showing me the newest
> people and show me the ones who'd actually suit me.

### Data

```
user_profile (
  user_id   PK FK users(id) ON DELETE CASCADE,
  age       int null,
  city      varchar(80) null,
  province  varchar(40) null,
  interests text[]  ,           -- from the existing INTEREST_VOCAB
  age_min, age_max  int null,
  updated_at timestamptz
)
```

This is the viewer's own data, freely given — it does not violate Principle 3.

### Ranking

A transparent score, not a black box. Shown as "why" on the card.

```
score = 3 * (shared interests / their interest count, capped at 3 shared)
      + 2 * (same city ? 1 : same province ? 0.5 : 0)
      + 1 * (age within preferred range ? 1 : falls off linearly over 10 years)
      + 0.5 * recency bucket (fresh=1, recent=0.5, stale=0)
```

Weights belong in one named constant block, not scattered — they will be
tuned, and per the project's own convention, tuned from measurement rather
than guessed.

Sort becomes a control: **Newest** (default, unchanged) / **Best match**
(requires profile). Never make "Best match" the default — a new user has no
profile and would see an arbitrary order.

### UI

- Sort dropdown in the list header (currently the static "Newest ▾").
- On each card in match mode: "3 shared interests · same city".
- Prompt to fill the profile appears once, dismissible, only when signed in.

### Rules

- Ranking is a *sort*, never a filter — nobody disappears because they score
  low.
- Never present it as compatibility or matchmaking. It's "sorted by overlap".
- Missing data (their age unknown) must not push someone to the bottom; treat
  unknown as neutral, not zero.

### Acceptance

- Profile with 0 interests → Best match is disabled with an explanation.
- Person with unknown age is not systematically ranked below one with a stated
  mismatched age.
- Switching sort never changes the result *count*.

**Effort:** M — two to three days.

---

## Spec 5 — Post composer

Independent of everything above; useful even signed out, better signed in.

### Correction to an earlier claim

I previously said the app "knows which posts drew replies". **It does not.**
`posts` stores id, subreddit, author, title, body, url and timestamps — no
comment count, and Reddit's Atom feed does not carry one. Any data-driven
advice needs Spec 5a first.

### Spec 5a — reply signal (prerequisite, optional)

To know what works, ingest a reply count per post. Reddit's `.json` endpoints
403 for non-browser clients (see `scraper.py`), so the options are:

- Fetch each post's own comments RSS and count entries — **1 request per
  post**, ~900 requests, at ~3s spacing that's 45 minutes. One-off backfill
  then incremental for new posts only. Viable but slow.
- Parse the HTML post page — fragile, breaks on redesign.

Recommend the RSS approach, run as a separate `manage.py backfill-replies`
command, rate-limited and resumable. Adds `Post.reply_count int null` and
`Post.replies_checked_at`.

**Effort:** M — one to two days. Do this only if Spec 5b proves wanted.

### Spec 5b — the composer itself

Without 5a, ship structural guidance, which is genuinely useful on its own:

- A form: age, gender, city, interests, what you're looking for, a free-text
  paragraph.
- Generates a well-structured post in Dutch or English (the extractor's own
  prompt inverted — the app already knows exactly which fields it wishes
  posts contained, because it spends all day failing to find them).
- A checklist derived from real gaps in the dataset, which *is* measurable
  today. Measured over the current 598 people:

  | Gap | Share |
  | --- | --- |
  | No usable location | 32% |
  | No interests identifiable | 18% |
  | No age stated | 13% |

  So: "32% of posts don't say where the person lives. Yours does ✓" — true,
  computed, and immediately actionable for someone writing a post.
- Copy button, plus a link to the right subreddit's submit page. **The app
  does not post on anyone's behalf.**

With 5a, add: "posts that mention a specific activity get N× more replies" —
only once that's actually computed, never asserted.

### Acceptance

- Composer output pasted into Reddit needs no editing to read naturally.
- Every statistic shown is computed from the live dataset, with the sample
  size visible.
- No OAuth-to-Reddit, no posting API, no draft stored server-side unless
  signed in.

**Effort:** M for 5b, plus M for 5a if wanted.

---

## Build order

| # | Spec | Depends on | Effort | Ship value |
| --- | --- | --- | --- | --- |
| 0 | `person_key` | — | S | none alone; unblocks everything |
| 1 | Finish sign-in | — | S/M | makes the account real |
| 2 | Saved / status / notes | 0, 1 | M | **highest per day spent** |
| 3 | Saved searches + alerts | 0, 1 | L + decision | **highest overall** |
| 4 | Profile + ranking | 0, 1 | M | medium |
| 5b | Composer | — | M | medium, no account needed |
| 5a | Reply signal | — | M | only if 5b lands well |

Recommended: **0 → 1 → 2**, ship, then decide between 3 and 4 based on whether
anyone actually saves anyone. If Spec 2 goes unused, Spec 3 will too, and
that's worth learning cheaply.

---

## Explicitly out of scope

**In-app posting and direct messaging.** Recorded here so the decision isn't
relitigated by accident:

- The dataset contains posts like *"18 and looking for friends in Assen"*.
  Hosting DMs means owning grooming, harassment and abuse reporting — a
  continuing duty with real human stakes, not a feature that ships once.
- User-generated content plus EU users brings DSA obligations and makes the
  operator a controller of message content.
- The app's pull is that it aggregates an *existing* population. An in-app
  inbox starts empty and competes with Reddit, where the audience already is.

If it's ever revisited, the safe order is: claimed profiles → opt-in contact
*requests* (not open DMs) → blocking and rate limits designed in from the
start, not retrofitted.
