import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteSearch,
  fetchMyProfile,
  fetchSearches,
  saveMyProfile,
  updateSearch,
} from "../api";
import { C } from "../theme";
import { INTEREST_VOCAB, PROVINCES } from "../types";
import type { Cadence, MyProfile } from "../types";

const heading: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: C.ink,
  margin: "28px 0 10px",
};

const field: React.CSSProperties = {
  border: `1px solid ${C.chipBorder}`,
  borderRadius: 7,
  padding: "7px 9px",
  fontSize: 12.5,
  fontFamily: "inherit",
  background: C.panel,
  color: C.ink,
};

/**
 * Spec 4 — the viewer's own details, used only to sort by overlap.
 *
 * Note this is data the viewer volunteers about themselves. It does not
 * expand what is known about the people on the map, who never signed up.
 */
export function MyProfileSection() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["my-profile"],
    queryFn: ({ signal }) => fetchMyProfile(signal),
  });

  const [draft, setDraft] = useState<MyProfile | null>(null);
  useEffect(() => {
    if (data && draft === null) setDraft(data);
  }, [data, draft]);

  const mutation = useMutation({
    mutationFn: (p: MyProfile) => saveMyProfile(p),
    onSuccess: (saved) => {
      setDraft(saved);
      qc.invalidateQueries({ queryKey: ["my-profile"] });
      // Ranking reads this, so any match-sorted list on screen is now stale.
      qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });

  if (!draft) return null;
  const set = (patch: Partial<MyProfile>) => setDraft({ ...draft, ...patch });

  return (
    <>
      <div style={heading}>About you</div>
      <div
        style={{
          fontSize: 12.5,
          color: C.muted,
          lineHeight: 1.6,
          marginBottom: 12,
        }}
      >
        Used only to offer a “best match” sort — how much someone overlaps with
        you. It is never shown to anyone else and never leaves this app.
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <input
          type="number"
          value={draft.age ?? ""}
          onChange={(e) =>
            set({ age: e.target.value ? Number(e.target.value) : null })
          }
          placeholder="Your age"
          style={{ ...field, width: 100 }}
        />
        <input
          value={draft.city ?? ""}
          onChange={(e) => set({ city: e.target.value || null })}
          placeholder="Your city"
          style={{ ...field, flex: 1, minWidth: 120 }}
        />
        <select
          value={draft.province ?? ""}
          onChange={(e) => set({ province: e.target.value || null })}
          style={{ ...field, flex: 1, minWidth: 140 }}
        >
          <option value="">Province…</option>
          {PROVINCES.map((pv) => (
            <option key={pv} value={pv}>
              {pv}
            </option>
          ))}
        </select>
      </div>

      <div
        style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}
      >
        <span style={{ fontSize: 12.5, color: C.muted }}>Ages I am after</span>
        <input
          type="number"
          value={draft.age_min ?? ""}
          onChange={(e) =>
            set({ age_min: e.target.value ? Number(e.target.value) : null })
          }
          placeholder="from"
          style={{ ...field, width: 80 }}
        />
        <input
          type="number"
          value={draft.age_max ?? ""}
          onChange={(e) =>
            set({ age_max: e.target.value ? Number(e.target.value) : null })
          }
          placeholder="to"
          style={{ ...field, width: 80 }}
        />
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
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

      <button
        onClick={() => mutation.mutate(draft)}
        disabled={mutation.isPending}
        style={{
          border: "none",
          background: C.accent,
          color: "#fff",
          borderRadius: 8,
          padding: "9px 18px",
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        {mutation.isPending ? "Saving…" : mutation.isSuccess ? "Saved ✓" : "Save"}
      </button>
    </>
  );
}

/** Spec 3 — standing alerts over a saved filter set. */
export function SavedSearchesSection() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["searches"],
    queryFn: ({ signal }) => fetchSearches(signal),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["searches"] });
  const cadenceMut = useMutation({
    mutationFn: ({ id, cadence }: { id: number; cadence: Cadence }) =>
      updateSearch(id, { cadence }),
    onSuccess: invalidate,
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteSearch(id),
    onSuccess: invalidate,
  });

  const searches = data ?? [];

  return (
    <>
      <div style={heading}>Alerts</div>
      {searches.length === 0 ? (
        <div style={{ fontSize: 12.5, color: C.muted, lineHeight: 1.6 }}>
          None yet. Set some filters on the map, then use “Alert me about new
          matches” in the filter panel. You will get an email when someone new
          fits, instead of having to check back.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {searches.map((s) => (
            <div
              key={s.id}
              style={{
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                padding: "10px 12px",
                background: C.panel,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.ink }}>
                  {s.name}
                </div>
                <div style={{ fontSize: 11.5, color: C.faint }}>
                  {s.last_match_at
                    ? `last match ${new Date(s.last_match_at).toLocaleDateString()}`
                    : "no matches yet"}
                </div>
              </div>
              <select
                value={s.cadence}
                onChange={(e) =>
                  cadenceMut.mutate({
                    id: s.id,
                    cadence: e.target.value as Cadence,
                  })
                }
                style={{ ...field, padding: "5px 7px", fontSize: 11.5 }}
              >
                <option value="weekly">Weekly</option>
                <option value="daily">Daily</option>
                <option value="off">Off</option>
              </select>
              <button
                onClick={() => deleteMut.mutate(s.id)}
                title="Delete this alert"
                style={{
                  border: "none",
                  background: "none",
                  color: C.faint2,
                  fontSize: 15,
                  cursor: "pointer",
                  padding: "0 4px",
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
