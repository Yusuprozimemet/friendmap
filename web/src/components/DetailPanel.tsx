import { useEffect, useState } from "react";
import { C, bucketOf, dotColors } from "../theme";
import { dateStr, headline, relTime } from "../format";
import { SaveButton } from "./SaveButton";
import type { Person, PersonStatus } from "../types";
import type { PersonStateApi } from "../usePersonState";

interface Props {
  person: Person;
  onBack: () => void;
  onAddInterest: (slug: string) => void;
  state: PersonStateApi;
  onSignIn: () => void;
}

const STATUS_OPTIONS: Array<{ value: PersonStatus | null; label: string }> = [
  { value: null, label: "—" },
  { value: "contacted", label: "Contacted" },
  { value: "hidden", label: "Not interested" },
];

export function DetailPanel({
  person: p,
  onBack,
  onAddInterest,
  state,
  onSignIn,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const dc = dotColors(bucketOf(p.days_ago));
  const mine = state.get(p.person_key);

  // Local draft so typing isn't fighting the server round trip; committed on
  // blur rather than per keystroke.
  const [note, setNote] = useState(mine?.note ?? "");
  useEffect(() => {
    setNote(mine?.note ?? "");
    // Reset when the panel switches to a different person, not on every
    // note change from our own optimistic update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.person_key]);

  return (
    <div style={{ overflowY: "auto", flex: 1 }}>
      <div style={{ padding: "16px 20px 0" }}>
        <button
          onClick={onBack}
          style={{
            border: "none",
            background: "none",
            color: C.muted,
            fontSize: 12.5,
            cursor: "pointer",
            padding: 0,
            marginBottom: 14,
            fontFamily: "inherit",
          }}
        >
          ← Back to results
        </button>
      </div>

      <div style={{ padding: "0 20px 24px" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 6,
          }}
        >
          <span
            style={{
              width: 11,
              height: 11,
              borderRadius: "50%",
              flexShrink: 0,
              background: dc.bg,
              border: dc.border,
            }}
          />
          <div style={{ fontSize: 17, fontWeight: 700, color: C.ink }}>
            {headline(p)}
          </div>
          <div style={{ marginLeft: "auto" }}>
            <SaveButton
              personKey={p.person_key}
              saved={mine?.saved ?? false}
              signedIn={state.signedIn}
              onToggle={() =>
                state.set(p.person_key, { saved: !(mine?.saved ?? false) })
              }
              onSignIn={onSignIn}
              size={30}
            />
          </div>
        </div>
        <div style={{ fontSize: 12.5, color: C.muted, marginBottom: 18 }}>
          Posted {relTime(p.days_ago)} · {dateStr(p.posted_at)}
          {p.precision === "province" && " · ~ approximate location"}
          {(p.precision === "none" || p.precision === "country") &&
            " · didn't say where — parked offshore on the map"}
        </div>

        <div
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: C.ink,
            marginBottom: 12,
            lineHeight: 1.4,
          }}
        >
          {p.title}
        </div>

        {/* Private to the signed-in viewer; nothing here reaches the person. */}
        {p.person_key && (
          <div
            style={{
              background: C.chipBg,
              border: `1px solid ${C.chipBorder}`,
              borderRadius: 10,
              padding: "12px 14px",
              marginBottom: 18,
            }}
          >
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                color: C.muted,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: 8,
              }}
            >
              My notes{" "}
              <span style={{ textTransform: "none", fontWeight: 400 }}>
                · private
              </span>
            </div>

            {state.signedIn ? (
              <>
                <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
                  {STATUS_OPTIONS.map((opt) => {
                    const active = (mine?.status ?? null) === opt.value;
                    return (
                      <button
                        key={opt.label}
                        onClick={() =>
                          state.set(p.person_key, {
                            set_status: true,
                            status: opt.value,
                          })
                        }
                        style={{
                          flex: 1,
                          border: `1px solid ${active ? C.accent : C.chipBorder}`,
                          background: active ? C.accentBg : C.panel,
                          color: active ? C.accentInk : C.body,
                          borderRadius: 7,
                          padding: "6px 0",
                          fontSize: 11.5,
                          fontWeight: 600,
                          cursor: "pointer",
                          fontFamily: "inherit",
                        }}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  onBlur={() => {
                    if (note !== (mine?.note ?? ""))
                      state.set(p.person_key, { note });
                  }}
                  placeholder="Messaged 3 Aug, no reply yet…"
                  rows={2}
                  style={{
                    width: "100%",
                    resize: "vertical",
                    border: `1px solid ${C.chipBorder}`,
                    borderRadius: 7,
                    padding: "8px 10px",
                    fontSize: 12.5,
                    fontFamily: "inherit",
                    color: C.ink,
                    background: C.panel,
                  }}
                />
              </>
            ) : (
              <div style={{ fontSize: 12.5, color: C.muted, lineHeight: 1.6 }}>
                <button
                  onClick={onSignIn}
                  style={{
                    border: "none",
                    background: "none",
                    padding: 0,
                    color: C.accent,
                    fontWeight: 600,
                    fontSize: 12.5,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  Sign in
                </button>{" "}
                to save this person, mark them contacted, and keep a note.
              </div>
            )}
          </div>
        )}

        {p.interests.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
              marginBottom: 18,
            }}
          >
            {p.interests.map((slug) => (
              <button
                key={slug}
                onClick={() => onAddInterest(slug)}
                title={`Filter by ${slug}`}
                style={{
                  border: `1px solid ${C.chipBorder}`,
                  background: C.chipBg,
                  color: C.body,
                  borderRadius: 20,
                  padding: "5px 11px",
                  fontSize: 12,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                {slug}
              </button>
            ))}
          </div>
        )}

        {p.summary && (
          <div
            style={{
              background: C.chipBg,
              borderRadius: 10,
              padding: "14px 16px",
              marginBottom: 18,
            }}
          >
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 600,
                color: C.amberInk,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: 6,
              }}
            >
              Summary
            </div>
            <div style={{ fontSize: 13.5, color: C.ink2, lineHeight: 1.55 }}>
              {p.summary}
            </div>
          </div>
        )}

        <div style={{ marginBottom: 18 }}>
          <div
            style={{
              fontSize: 10.5,
              fontWeight: 600,
              color: C.muted,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              marginBottom: 8,
            }}
          >
            Original post{" "}
            <span style={{ textTransform: "none", fontWeight: 400 }}>
              · {p.lang === "nl" ? "Dutch" : "English"}
            </span>
          </div>
          {/* Never auto-translated — it stays in the language they wrote it in. */}
          <div
            style={{
              fontSize: 14.5,
              color: C.ink,
              lineHeight: 1.65,
              fontFamily: "Georgia, serif",
              whiteSpace: "pre-wrap",
              ...(expanded
                ? {}
                : {
                    display: "-webkit-box",
                    WebkitLineClamp: 6,
                    WebkitBoxOrient: "vertical" as const,
                    overflow: "hidden",
                  }),
            }}
          >
            {p.body || "(no body text)"}
          </div>
          {p.body.length > 240 && (
            <button
              onClick={() => setExpanded((v) => !v)}
              style={{
                border: "none",
                background: "none",
                color: C.accent,
                fontWeight: 600,
                fontSize: 12.5,
                cursor: "pointer",
                padding: "8px 0 0",
                fontFamily: "inherit",
              }}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>

        <div
          style={{
            fontSize: 12,
            color: C.faint,
            marginBottom: 20,
            lineHeight: 1.7,
          }}
        >
          r/{p.subreddit} · posted {dateStr(p.posted_at)}
          {p.repeat_count > 0 && (
            <>
              <br />
              Also posted {p.repeat_count}× before
            </>
          )}
        </div>

        {/* The only outbound action. No messaging, no saving — by design. */}
        <a
          href={p.permalink}
          target="_blank"
          rel="noreferrer noopener"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 6,
            background: C.accent,
            color: C.panel,
            textDecoration: "none",
            padding: 12,
            borderRadius: 10,
            fontSize: 14,
            fontWeight: 600,
          }}
        >
          Open on Reddit ↗
        </a>
      </div>
    </div>
  );
}
