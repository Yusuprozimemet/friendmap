import { C } from "../theme";

const para: React.CSSProperties = {
  fontSize: 14.5,
  color: C.ink2,
  lineHeight: 1.75,
  marginBottom: 20,
};

const heading: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: C.ink,
  margin: "28px 0 10px",
};

// Plain anchor, not target="_blank": /privacy is served by this app, so it is
// the same origin and opening a new tab would be gratuitous.
const link: React.CSSProperties = { color: C.accent };

export function AboutView({ subreddits }: { subreddits: string[] }) {
  const links = subreddits.map((s, i) => (
    <span key={s}>
      {i > 0 && (i === subreddits.length - 1 ? " and " : ", ")}
      <a
        href={`https://reddit.com/r/${s}`}
        target="_blank"
        rel="noreferrer noopener"
        style={{ color: C.accent }}
      >
        r/{s}
      </a>
    </span>
  ));

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "48px 24px" }}>
      <div style={{ maxWidth: 640, margin: "0 auto" }}>
        <div
          style={{ fontSize: 22, fontWeight: 700, color: C.ink, marginBottom: 16 }}
        >
          About FriendMap NL
        </div>
        <div style={para}>
          FriendMap NL reads public posts from {links} once a day, pulls out the
          useful details with a language model — age, location, interests, what
          someone's looking for — and plots them on a map of the Netherlands.
        </div>
        {subreddits.length > 1 && (
          <div style={para}>
            Plenty of people post the same appeal to more than one of these
            subreddits. They appear once here, under their most recent post —
            you won't see the same person twice because they cast a wide net.
          </div>
        )}
        <div style={para}>
          It's a browser, not a network. There's no messaging, and nothing is
          ever sent to anyone on your behalf. Every card links straight back to
          the original Reddit post — that's where any actual conversation
          happens.
        </div>
        <div style={para}>
          Signing in is optional. It adds a saved list, private notes, and email
          alerts for a search you saved — all of it visible only to you, and none
          of it visible to the people on the map. You can delete your account and
          everything attached to it at any time from your account page.
        </div>

        <div style={heading}>How current is this?</div>
        <div style={para}>
          The ingest job runs daily. Posts older than 30 days are hidden by
          default because most people move on within a few weeks. Deleted or
          removed Reddit posts are checked daily too and dropped from the map.
        </div>

        <div style={heading}>How precise is the location?</div>
        <div style={para}>
          City level at most — never an address, never a guess. When someone only
          names a province, they appear as a soft blur over that province rather
          than a pin. People who didn't say where they live aren't guessed at or
          hidden: they sit together in a marked group off the coast, labelled
          "no location given", so it's obvious the position means nothing.
        </div>

        <div style={heading}>I want my post removed</div>
        <div style={para}>
          Delete the original post on Reddit — it will be purged from FriendMap NL
          within a day. Or ask directly, using the contact address on the{" "}
          <a href="/privacy" style={link}>
            privacy page
          </a>
          : a requested removal is permanent, because it's recorded so later
          scrapes can't put it back. You don't have to give a reason.
        </div>

        <div style={heading}>What's held, and on what basis</div>
        <div style={para}>
          The{" "}
          <a href="/privacy" style={link}>
            privacy notice
          </a>{" "}
          covers all of it: what's extracted, what's deliberately not (no health,
          sexuality, religion or ethnicity — ever), who processes it, how long
          it's kept, and your rights. Usernames are never published by this site.
        </div>
      </div>
    </div>
  );
}
