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
          It's a browser, not a network. There's no messaging, no accounts, no
          saved lists. Every card links straight back to the original Reddit post
          — that's where any actual conversation happens.
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
          within a day. If you need it gone sooner, reach out and it'll be removed
          by hand.
        </div>
      </div>
    </div>
  );
}
