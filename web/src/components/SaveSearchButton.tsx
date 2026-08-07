import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createSearch, filtersToParams } from "../api";
import { C } from "../theme";
import type { Cadence, Filters } from "../types";

interface Props {
  filters: Filters;
  activeLabels: string[];
  signedIn: boolean;
  onSignIn: () => void;
}

/** Turns the current filter set into a standing alert. */
export function SaveSearchButton({
  filters,
  activeLabels,
  signedIn,
  onSignIn,
}: Props) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  // Weekly by default: at roughly five new people a week per subreddit, daily
  // would mostly be an email saying nothing happened.
  const [cadence, setCadence] = useState<Cadence>("weekly");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const suggested = activeLabels.slice(0, 3).join(" · ") || "Everyone";

  const mutation = useMutation({
    mutationFn: () => {
      // Reuse the exact query string the list is showing, so the alert can't
      // mean something different from what's on screen.
      const filterObject = Object.fromEntries(filtersToParams(filters).entries());
      return createSearch(name.trim() || suggested, filterObject, cadence);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["searches"] });
      setOpen(false);
      setName("");
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  if (!open) {
    return (
      <button
        onClick={() => (signedIn ? setOpen(true) : onSignIn())}
        style={{
          width: "100%",
          border: `1px solid ${C.chipBorder}`,
          background: C.chipBg,
          color: C.body,
          borderRadius: 8,
          padding: "9px 0",
          fontSize: 12.5,
          fontWeight: 600,
          cursor: "pointer",
          fontFamily: "inherit",
          marginBottom: 22,
        }}
      >
        {signedIn ? "🔔 Alert me about new matches" : "Sign in to get alerts"}
      </button>
    );
  }

  return (
    <div
      style={{
        border: `1px solid ${C.accent}`,
        background: C.accentSel,
        borderRadius: 10,
        padding: 12,
        marginBottom: 22,
      }}
    >
      <div style={{ fontSize: 12, fontWeight: 600, color: C.ink, marginBottom: 8 }}>
        Email me when someone new matches
      </div>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={suggested}
        style={{
          width: "100%",
          border: `1px solid ${C.chipBorder}`,
          borderRadius: 7,
          padding: "7px 9px",
          fontSize: 12,
          fontFamily: "inherit",
          marginBottom: 8,
          background: C.panel,
          color: C.ink,
        }}
      />
      <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
        {(["weekly", "daily"] as const).map((c) => (
          <button
            key={c}
            onClick={() => setCadence(c)}
            style={{
              flex: 1,
              border: `1px solid ${cadence === c ? C.accent : C.chipBorder}`,
              background: cadence === c ? C.accentBg : C.panel,
              color: cadence === c ? C.accentInk : C.body,
              borderRadius: 7,
              padding: "6px 0",
              fontSize: 11.5,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            {c === "weekly" ? "Weekly" : "Daily"}
          </button>
        ))}
      </div>
      {error && (
        <div style={{ fontSize: 11.5, color: "#A33B2A", marginBottom: 8 }}>
          {error}
        </div>
      )}
      <div style={{ display: "flex", gap: 6 }}>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          style={{
            flex: 1,
            border: "none",
            background: C.accent,
            color: "#fff",
            borderRadius: 7,
            padding: "8px 0",
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          {mutation.isPending ? "Saving…" : "Save"}
        </button>
        <button
          onClick={() => {
            setOpen(false);
            setError(null);
          }}
          style={{
            border: `1px solid ${C.chipBorder}`,
            background: C.panel,
            color: C.body,
            borderRadius: 7,
            padding: "8px 12px",
            fontSize: 12,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
