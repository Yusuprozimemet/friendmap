import { useState } from "react";

import { MyProfileSection, SavedSearchesSection } from "./AccountSections";
import { C } from "../theme";
import type { AuthUser } from "../types";
import type { PersonStateApi } from "../usePersonState";

const heading: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 700,
  color: C.ink,
  margin: "28px 0 10px",
};

interface Props {
  user: AuthUser;
  state: PersonStateApi;
  onSignOut: () => void;
  onDelete: () => Promise<void>;
}

export function AccountView({ user, state, onSignOut, onDelete }: Props) {
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canDelete = confirm.trim().toLowerCase() === "delete";

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "48px 24px" }}>
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <div
          style={{ fontSize: 22, fontWeight: 700, color: C.ink, marginBottom: 6 }}
        >
          Your account
        </div>
        <div style={{ fontSize: 13.5, color: C.muted, marginBottom: 4 }}>
          {user.name}
        </div>
        <div style={{ fontSize: 13.5, color: C.muted }}>{user.email}</div>

        <div style={heading}>What's on your list</div>
        <div
          style={{
            display: "flex",
            gap: 10,
            marginBottom: 6,
          }}
        >
          {(
            [
              ["Saved", state.savedCount],
              ["Contacted", state.contactedCount],
              ["Not interested", state.hiddenCount],
            ] as const
          ).map(([label, n]) => (
            <div
              key={label}
              style={{
                flex: 1,
                border: `1px solid ${C.border}`,
                borderRadius: 10,
                padding: "12px 14px",
                background: C.panel,
              }}
            >
              <div style={{ fontSize: 21, fontWeight: 700, color: C.ink }}>
                {n}
              </div>
              <div style={{ fontSize: 11.5, color: C.muted }}>{label}</div>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 12, color: C.faint, lineHeight: 1.6 }}>
          Only you can see any of this. Nothing you record here is shown to the
          people on the map, and nothing is sent to Reddit.
        </div>

        <MyProfileSection />
        <SavedSearchesSection />

        <div style={heading}>Sign out</div>
        <button
          onClick={onSignOut}
          style={{
            border: `1px solid ${C.border}`,
            background: C.panel,
            color: C.body,
            borderRadius: 8,
            padding: "9px 16px",
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          Sign out
        </button>

        <div style={{ ...heading, color: C.amberInk }}>Delete your account</div>
        <div
          style={{
            border: `1px solid ${C.chipBorder}`,
            background: C.amberBg,
            borderRadius: 10,
            padding: "14px 16px",
          }}
        >
          <div
            style={{
              fontSize: 13,
              color: C.amberInk,
              lineHeight: 1.65,
              marginBottom: 12,
            }}
          >
            This removes your account and everything saved with it — your{" "}
            {state.savedCount + state.contactedCount + state.hiddenCount} marked
            people and every note. It cannot be undone, and it doesn't affect
            anything on Reddit.
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Type DELETE to confirm"
              style={{
                flex: 1,
                border: `1px solid ${C.chipBorder}`,
                borderRadius: 7,
                padding: "8px 10px",
                fontSize: 12.5,
                fontFamily: "inherit",
                background: C.panel,
                color: C.ink,
              }}
            />
            <button
              disabled={!canDelete || busy}
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  await onDelete();
                } catch {
                  setError("Couldn't delete the account — please try again.");
                } finally {
                  setBusy(false);
                }
              }}
              style={{
                border: "none",
                background: canDelete ? "#A33B2A" : C.chipBorder,
                color: canDelete ? "#fff" : C.faint,
                borderRadius: 7,
                padding: "9px 16px",
                fontSize: 12.5,
                fontWeight: 700,
                cursor: canDelete && !busy ? "pointer" : "not-allowed",
                fontFamily: "inherit",
                whiteSpace: "nowrap",
              }}
            >
              {busy ? "Deleting…" : "Delete"}
            </button>
          </div>
          {error && (
            <div style={{ fontSize: 12, color: "#A33B2A", marginTop: 8 }}>
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
