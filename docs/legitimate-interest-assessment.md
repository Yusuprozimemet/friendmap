# Legitimate interest assessment

Art. 6(1)(f) GDPR is the basis for processing the posts that appear on the map.
It requires a documented balancing test, and the test is only meaningful if it
can come out negative — so the mitigations below are recorded as things the code
actually does, each one checkable in the source.

This covers **only** the people whose Reddit posts are collected. Signed-in
accounts are Art. 6(1)(b) — they asked for the service — and are not in scope
here.

Not legal advice. This is the engineering record of a decision; a lawyer should
review it before this is operated at any scale.

---

## 1. Purpose test — is there a legitimate interest?

To let people looking for friends in the Netherlands find each other by place,
age and shared interest, rather than by scrolling an unstructured subreddit feed
in reverse-chronological order.

The interest is real, and it is largely the *same* interest the data subjects
have: they published a post asking to be found. A tool that makes those posts
easier to find serves the author's stated goal. That alignment is the strongest
thing this assessment has going for it, and most of the design follows from
protecting it.

Third-party interest: other people in the same subreddits, who want to find
someone nearby. That is who the site is for.

## 2. Necessity test — is processing necessary for that purpose?

Yes, and the scope is bounded by the purpose:

- A map needs a location, so location is extracted.
- Filtering by age and interest needs age and interests.
- Deciding whether a post is still relevant needs a timestamp.
- **Nothing else is extracted.** The vocabulary is a closed list of 23 interest
  tags; the model cannot invent a 24th.

Could the purpose be achieved with less? Aggregating without storing was
considered and rejected: it would mean re-scraping on every page load, which is
both heavier on Reddit and worse for the data subjects, since the app would then
need no memory of who asked to be removed.

## 3. Balancing test — do the subjects' rights override it?

### Factors against the processing

These are the real ones, stated plainly:

1. **No consent, no awareness.** Nobody posting in r/makenewfriendsNL expects a
   structured database of themselves. Art. 14 exists precisely because this is a
   surprise.
2. **Aggregation changes the character of the data.** One public post is one
   public post. Several hundred, sorted by age, gender, city and interest, is a
   different artefact, and it is the artefact this app creates.
3. **Inference.** Age and gender are *derived by a language model* from prose,
   not copied from a field. Derived data can be wrong about a real person.
4. **The subjects are often vulnerable.** People looking for friends are
   disproportionately new arrivals, isolated, or going through a life change.
   Many posts say so. That raises the stakes on getting this right.
5. **Children.** Age is extracted and some posters are under 18.

### Mitigations actually implemented

| Risk | What the code does |
| --- | --- |
| Identification | The Reddit username is **never** served by the API — excluded from the response model, not merely omitted by convention. The per-person identifier is a keyed HMAC, so it cannot be reversed with a username wordlist. |
| Aggregation harm | `noindex, nofollow, noarchive` as both a meta tag and a response header, plus `robots.txt` disallow. The aggregate is not searchable, so it cannot become someone's Google result. |
| Bulk re-use | Per-IP token-bucket rate limiting on the API. |
| Special-category data | The interest vocabulary deliberately excludes health, mental health, sexuality, religion, ethnicity and political opinion, all of which appear in the posts. `INTEREST_VOCAB` in `app/models.py` records this decision and its reasoning. Loneliness and mental health were measured at 9.2% of posts and still left out. |
| Inaccuracy | Every card shows the original post text and links to the original post, so any inference can be checked against the source. Low-confidence extractions are flagged. Location is never guessed: an unplaced person is shown as explicitly unplaced rather than pinned somewhere plausible. |
| Precision | City level at most. Province-only posts render as a blur over the province, not a pin. No addresses, ever. |
| Contact risk | **The app has no messaging.** It cannot contact anyone on anyone's behalf. Every conversation happens back on Reddit, under Reddit's own rules and blocking. |
| Persistence | Posts deleted on Reddit are detected daily and dropped. Posts past `RETENTION_DAYS` are deleted outright, not merely hidden. |
| Objection | Any removal request is honoured without asking for a reason, and recorded in `suppressions` so the next scrape cannot undo it — see `manage.py suppress`. Removal by person, not just by post, is supported. |

### Factors still unresolved

Recorded rather than glossed over:

- **Art. 14 notice cannot realistically reach each subject individually.** There
  is no way to message a Reddit user without an account and without contacting
  them, which the app deliberately cannot do. This relies on Art. 14(5)(b)
  (disproportionate effort) with a public notice at `/privacy` as the
  compensating measure. That is a defensible reading, not a certain one.
- **Minors.** Age is extracted but nothing is done differently for a stated age
  under 18. The honest options are to exclude them from the map or to treat them
  the same as anyone else; currently it is the latter, by omission rather than by
  decision. **This should be decided deliberately.**
- **The `needs_review` flag is not acted on.** Low-confidence extractions are
  marked and then displayed anyway.

## 4. Conclusion

The processing is defensible on Art. 6(1)(f) as built, resting mainly on: the
posts are already public and were written to be found, the app adds no capability
to contact anyone, the aggregate is excluded from search engines, no
special-category data is inferred, and objection is honoured on request and made
durable.

It would stop being defensible if any of the following changed, so each is a
tripwire rather than a preference:

- Making the site indexable, or dropping the `noindex` headers.
- Adding any way to contact a person from inside the app.
- Extending the vocabulary to health, sexuality, religion, ethnicity or politics.
- Publishing usernames, or making the person key reversible.
- Removing the removal route, or letting the scrape override a suppression.
- Selling, sharing for advertising, or training a model on the collected text.

## 5. Review

Reassess when the sources, the extracted fields, the retention period, or the
audience change — and in any case if the corpus grows by an order of magnitude,
since the aggregation argument in §3 gets stronger the larger it gets.

| | |
| --- | --- |
| First written | 2026-08-07 |
| Controller | see `CONTROLLER_NAME` in the deployment environment |
| Next review | on any change above, or 2027-02-07 |