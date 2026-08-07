import { useEffect, useRef, useState } from "react";

import { C } from "../theme";
import type { AuthUser } from "../types";

interface Props {
  user: AuthUser | null;
  enabled: boolean;
  onSignIn: () => void;
  onSignOut: () => void;
  onOpenAccount: () => void;
}

const IS_LOCAL =
  typeof window !== "undefined" &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname);

/** Google's mark, inlined — a remote image would be blocked and adds a beacon. */
function GoogleMark() {
  return (
    <svg width="15" height="15" viewBox="0 0 48 48" aria-hidden>
      <path
        fill="#EA4335"
        d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.6 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.8 6.1C12.3 13.3 17.6 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.1 24.6c0-1.6-.1-3.1-.4-4.6H24v9.1h12.4c-.5 2.9-2.2 5.3-4.6 7l7.1 5.5c4.2-3.8 6.6-9.5 6.6-16z"
      />
      <path
        fill="#FBBC05"
        d="M10.4 28.7c-.5-1.4-.8-2.9-.8-4.7s.3-3.3.8-4.7l-7.8-6.1C1 16.4 0 20.1 0 24s1 7.6 2.6 10.8l7.8-6.1z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.1-5.5c-2 1.3-4.6 2.1-8.8 2.1-6.4 0-11.7-3.8-13.6-9.1l-7.8 6.1C6.5 42.6 14.6 48 24 48z"
      />
    </svg>
  );
}

export function AccountMenu({
  user,
  enabled,
  onSignIn,
  onSignOut,
  onOpenAccount,
}: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // No credentials on the server: don't offer a button that can only fail.
  // In development say so, because silence reads as "broken" not "off".
  if (!enabled) {
    if (!IS_LOCAL) return null;
    return (
      <span
        title="Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and SESSION_SECRET in friendsMap/.env — see the README"
        style={{
          fontSize: 11.5,
          color: C.faint2,
          border: `1px dashed ${C.border}`,
          borderRadius: 7,
          padding: "5px 10px",
          cursor: "help",
        }}
      >
        Sign-in not configured
      </span>
    );
  }

  if (!user) {
    return (
      <button
        onClick={onSignIn}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          height: 32,
          padding: "0 12px",
          borderRadius: 8,
          border: `1px solid ${C.border}`,
          background: C.panel,
          color: C.body,
          fontSize: 12.5,
          fontWeight: 600,
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        <GoogleMark />
        Sign in
      </button>
    );
  }

  const initial = (user.name || user.email || "?").trim().charAt(0).toUpperCase();

  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        title={user.email}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          height: 32,
          padding: "0 8px 0 4px",
          borderRadius: 8,
          border: `1px solid ${open ? C.accent : C.border}`,
          background: C.panel,
          color: C.body,
          fontSize: 12.5,
          fontWeight: 600,
          cursor: "pointer",
          fontFamily: "inherit",
        }}
      >
        {user.picture ? (
          <img
            src={user.picture}
            alt=""
            referrerPolicy="no-referrer"
            style={{ width: 24, height: 24, borderRadius: "50%" }}
          />
        ) : (
          <span
            style={{
              width: 24,
              height: 24,
              borderRadius: "50%",
              background: C.accentBg,
              color: C.accentInk,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
            }}
          >
            {initial}
          </span>
        )}
        {user.name.split(" ")[0] || "Account"}
        <span style={{ fontSize: 9, color: C.faint2 }}>▾</span>
      </button>

      {open && (
        <div
          style={{
            position: "absolute",
            right: 0,
            top: 38,
            minWidth: 210,
            background: C.panel,
            border: `1px solid ${C.border}`,
            borderRadius: 10,
            boxShadow: "0 6px 20px rgba(0,0,0,0.10)",
            padding: 6,
            zIndex: 50,
          }}
        >
          <div
            style={{
              padding: "8px 10px 10px",
              borderBottom: `1px solid ${C.divider}`,
              marginBottom: 6,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 700, color: C.ink }}>
              {user.name || "Signed in"}
            </div>
            <div
              style={{
                fontSize: 11.5,
                color: C.muted,
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {user.email}
            </div>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              onOpenAccount();
            }}
            style={{
              width: "100%",
              textAlign: "left",
              border: "none",
              background: "none",
              padding: "8px 10px",
              borderRadius: 6,
              fontSize: 12.5,
              color: C.body,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Your account
          </button>
          <button
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
            style={{
              width: "100%",
              textAlign: "left",
              border: "none",
              background: "none",
              padding: "8px 10px",
              borderRadius: 6,
              fontSize: 12.5,
              color: C.body,
              cursor: "pointer",
              fontFamily: "inherit",
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
