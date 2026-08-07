import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchWritingTips } from "../api";
import { C } from "../theme";
import { INTEREST_VOCAB } from "../types";
import { EMPTY_DRAFT, buildBody, buildTitle, checklist } from "../postDraft";
import type { Draft } from "../postDraft";

const heading: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: C.ink,
  margin: "24px 0 10px",
};

const field: React.CSSProperties = {
  border: `1px solid ${C.chipBorder}`,
  borderRadius: 7,
  padding: "8px 10px",
  fontSize: 13,
  fontFamily: "inherit",
  background: C.panel,
  color: C.ink,
};

export function ComposeView({ subreddits }: { subreddits: string[] }) {
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [copied, setCopied] = useState(false);

  const { data: tips } = useQuery({
    queryKey: ["writing-tips"],
    queryFn: ({ signal }) => fetchWritingTips(signal),
  });

  const set = (patch: Partial<Draft>) => {
    setDraft({ ...draft, ...patch });
    setCopied(false);
  };

  const title = buildTitle(draft);
  const body = buildBody(draft);
  const full = `${title}\n\n${body}`;

  const gaps = useMemo(() => {
    const out: Record<string, number> = {};
    for (const g of tips?.gaps ?? []) out[g.label] = g.count;
    return out;
  }, [tips]);

  const items = checklist(
    draft,
    gaps,
    tips?.sample_size ?? 0,
    tips?.median_length ?? 0,
  );
  const done = items.filter((i) => i.done).length;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "40px 24px" }}>
      <div style={{ maxWidth: 940, margin: "0 auto" }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: C.ink, marginBottom: 8 }}>
          Write a post that gets replies
        </div>
        <div
          style={{
            fontSize: 14,
            color: C.muted,
            lineHeight: 1.7,
            marginBottom: 4,
            maxWidth: 640,
          }}
        >
          Fill this in and copy the result into Reddit. The checklist comes from
          what is actually missing across the {tips?.sample_size ?? "…"} posts on
          the board — not from opinion.
        </div>
        <div style={{ fontSize: 12.5, color: C.faint, marginBottom: 8 }}>
          Nothing here is saved or posted for you. It only ever produces text to
          copy.
        </div>

        <div
          style={{
            display: "flex",
            gap: 28,
            alignItems: "flex-start",
            flexWrap: "wrap",
          }}
        >
          {/* --- form --- */}
          <div style={{ flex: "1 1 380px", minWidth: 320 }}>
            <div style={heading}>About you</div>
            <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
              <input
                value={draft.age}
                onChange={(e) => set({ age: e.target.value.replace(/\D/g, "").slice(0, 2) })}
                placeholder="Age"
                style={{ ...field, width: 76 }}
              />
              <select
                value={draft.gender}
                onChange={(e) => set({ gender: e.target.value })}
                style={{ ...field, width: 96 }}
              >
                <option value="">—</option>
                <option value="M">M</option>
                <option value="F">F</option>
                <option value="NB">NB</option>
              </select>
              <input
                value={draft.city}
                onChange={(e) => set({ city: e.target.value })}
                placeholder="Your city"
                style={{ ...field, flex: 1, minWidth: 120 }}
              />
            </div>

            <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
              {(["nl", "en"] as const).map((code) => (
                <button
                  key={code}
                  onClick={() => set({ lang: code })}
                  style={{
                    flex: 1,
                    border: `1px solid ${draft.lang === code ? C.accent : C.chipBorder}`,
                    background: draft.lang === code ? C.accentBg : C.panel,
                    color: draft.lang === code ? C.accentInk : C.body,
                    borderRadius: 7,
                    padding: "7px 0",
                    fontSize: 12.5,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  {code === "nl" ? "Dutch" : "English"}
                </button>
              ))}
            </div>
            <div style={{ fontSize: 11.5, color: C.faint, marginBottom: 4 }}>
              Write in whichever you're most comfortable with — both are normal
              on these subreddits.
            </div>

            <div style={heading}>What you're into</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {INTEREST_VOCAB.map((slug) => {
                const on = draft.interests.includes(slug);
                return (
                  <button
                    key={slug}
                    onClick={() =>
                      set({
                        interests: on
                          ? draft.interests.filter((i) => i !== slug)
                          : [...draft.interests, slug],
                      })
                    }
                    style={{
                      border: `1px solid ${on ? C.accent : C.chipBorder}`,
                      background: on ? C.accentBg : C.chipBg,
                      color: on ? C.accentInk : C.body,
                      borderRadius: 14,
                      padding: "5px 10px",
                      fontSize: 11.5,
                      fontWeight: 600,
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    {slug}
                  </button>
                );
              })}
            </div>

            <div style={heading}>What are you actually after?</div>
            <input
              value={draft.lookingFor}
              onChange={(e) => set({ lookingFor: e.target.value })}
              placeholder="someone to grab coffee with · a gym buddy · people to game with"
              style={{ ...field, width: "100%" }}
            />

            <div style={heading}>A few sentences in your own words</div>
            <textarea
              value={draft.about}
              onChange={(e) => set({ about: e.target.value })}
              rows={6}
              placeholder="What you do, what your week looks like, what you'd like to change. This is the part people reply to — the rest is just findable detail."
              style={{ ...field, width: "100%", resize: "vertical", lineHeight: 1.6 }}
            />
          </div>

          {/* --- preview + checklist --- */}
          <div style={{ flex: "1 1 380px", minWidth: 320 }}>
            <div style={heading}>
              Your post{" "}
              <span style={{ fontWeight: 400, color: C.faint }}>
                · {full.length} characters
              </span>
            </div>
            <div
              style={{
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                background: C.panel,
                padding: 16,
              }}
            >
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: C.ink,
                  marginBottom: 10,
                  lineHeight: 1.4,
                }}
              >
                {title}
              </div>
              <div
                style={{
                  fontSize: 14,
                  color: C.ink2,
                  lineHeight: 1.65,
                  whiteSpace: "pre-wrap",
                  fontFamily: "Georgia, serif",
                }}
              >
                {body}
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              <button
                onClick={async () => {
                  await navigator.clipboard.writeText(full);
                  setCopied(true);
                }}
                style={{
                  border: "none",
                  background: C.accent,
                  color: "#fff",
                  borderRadius: 8,
                  padding: "10px 18px",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                {copied ? "Copied ✓" : "Copy post"}
              </button>
              {subreddits.map((s) => (
                <a
                  key={s}
                  href={`https://www.reddit.com/r/${s}/submit`}
                  target="_blank"
                  rel="noreferrer noopener"
                  style={{
                    border: `1px solid ${C.chipBorder}`,
                    background: C.chipBg,
                    color: C.body,
                    borderRadius: 8,
                    padding: "10px 14px",
                    fontSize: 12.5,
                    fontWeight: 600,
                    textDecoration: "none",
                    fontFamily: "inherit",
                  }}
                >
                  Post to r/{s} ↗
                </a>
              ))}
            </div>

            <div style={heading}>
              Checklist{" "}
              <span style={{ fontWeight: 400, color: C.faint }}>
                · {done} of {items.length}
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {items.map((item) => (
                <div
                  key={item.key}
                  style={{
                    display: "flex",
                    gap: 9,
                    alignItems: "flex-start",
                    opacity: item.done ? 1 : 0.85,
                  }}
                >
                  <span
                    style={{
                      width: 17,
                      height: 17,
                      borderRadius: "50%",
                      flexShrink: 0,
                      marginTop: 1,
                      background: item.done ? C.accent : "transparent",
                      border: item.done ? "none" : `2px solid ${C.chipBorder}`,
                      color: "#fff",
                      fontSize: 10.5,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: 700,
                    }}
                  >
                    {item.done ? "✓" : ""}
                  </span>
                  <div>
                    <div
                      style={{
                        fontSize: 13,
                        color: item.done ? C.ink : C.body,
                        fontWeight: item.done ? 600 : 500,
                      }}
                    >
                      {item.label}
                    </div>
                    {item.stat && (
                      <div style={{ fontSize: 11.5, color: C.faint, lineHeight: 1.5 }}>
                        {item.stat}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {tips && (
              <div
                style={{
                  marginTop: 16,
                  fontSize: 11.5,
                  color: C.faint,
                  lineHeight: 1.6,
                  borderTop: `1px solid ${C.divider}`,
                  paddingTop: 12,
                }}
              >
                Measured over {tips.sample_size} posts. This board can't tell you
                which posts got <em>replies</em> — Reddit's feed doesn't carry
                comment counts — so nothing here claims to. It only reports what
                other posts leave out.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
