import { C } from "../theme";

interface Props {
  personKey: string;
  saved: boolean;
  signedIn: boolean;
  onToggle: () => void;
  onSignIn: () => void;
  size?: number;
}

/**
 * Deliberately visible when signed out — this is the main reason anyone would
 * make an account, so hiding it would hide the pitch. Clicking it signs you in.
 */
export function SaveButton({
  personKey,
  saved,
  signedIn,
  onToggle,
  onSignIn,
  size = 26,
}: Props) {
  // A person with no key (deleted Reddit account) can't be tracked at all.
  if (!personKey) return null;

  const title = !signedIn
    ? "Sign in to save this person"
    : saved
      ? "Saved — click to remove"
      : "Save for later";

  return (
    <button
      title={title}
      aria-label={title}
      aria-pressed={saved}
      onClick={(e) => {
        e.stopPropagation();
        if (signedIn) onToggle();
        else onSignIn();
      }}
      style={{
        width: size,
        height: size,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        borderRadius: 7,
        border: "none",
        background: saved ? C.accentBg : "transparent",
        color: saved ? C.accent : C.faint2,
        cursor: "pointer",
        fontFamily: "inherit",
        padding: 0,
      }}
    >
      <svg
        width={size * 0.58}
        height={size * 0.58}
        viewBox="0 0 24 24"
        fill={saved ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
      </svg>
    </button>
  );
}
