import { C } from "../theme";
import type { Stats } from "../types";

const card: React.CSSProperties = {
  background: C.panel,
  border: `1px solid ${C.border}`,
  borderRadius: 12,
  padding: 20,
};

const cardTitle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: C.body,
  marginBottom: 14,
};

function BarRow({
  label,
  count,
  max,
  color,
}: {
  label: string;
  count: number;
  max: number;
  color: string;
}) {
  return (
    <div style={{ marginBottom: 9 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 12,
          color: C.body,
          marginBottom: 3,
        }}
      >
        <span>{label}</span>
        <span style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
          {count}
        </span>
      </div>
      <div style={{ background: C.divider, borderRadius: 4, height: 6 }}>
        <div
          style={{
            background: color,
            borderRadius: 4,
            height: 6,
            width: `${(count / max) * 100}%`,
          }}
        />
      </div>
    </div>
  );
}

export function InsightsView({ stats }: { stats: Stats | null }) {
  if (!stats) {
    return (
      <div style={{ padding: 48, color: C.faint, fontSize: 13 }}>Loading…</div>
    );
  }

  const tiles = [
    { label: "Active people (30d)", value: stats.active_30d },
    { label: "New this week", value: stats.new_this_week },
    { label: "Cities covered", value: stats.cities_covered },
    { label: "Median age", value: stats.median_age ?? "—" },
  ];

  const maxWeek = Math.max(1, ...stats.posts_per_week);
  const maxCity = Math.max(1, ...stats.top_cities.map((c) => c.count));
  const maxInterest = Math.max(1, ...stats.interest_counts.map((c) => c.count));
  const maxAge = Math.max(1, ...stats.age_buckets.map((c) => c.count));

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "32px 48px",
        maxWidth: 1100,
        margin: "0 auto",
        width: "100%",
      }}
    >
      <div style={{ fontSize: 20, fontWeight: 700, color: C.ink, marginBottom: 4 }}>
        Insights
      </div>
      <div style={{ fontSize: 13, color: C.faint, marginBottom: 28 }}>
        A quiet look at the last few months. Not affected by Explore filters.
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4,1fr)",
          gap: 14,
          marginBottom: 32,
        }}
      >
        {tiles.map((t) => (
          <div key={t.label} style={{ ...card, padding: 18 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: C.faint,
                textTransform: "uppercase",
                letterSpacing: "0.04em",
                marginBottom: 8,
              }}
            >
              {t.label}
            </div>
            <div
              style={{
                fontSize: 26,
                fontWeight: 700,
                color: C.ink,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {t.value}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.3fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div style={card}>
          <div style={{ ...cardTitle, marginBottom: 16 }}>Posts per week</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 120 }}>
            {stats.posts_per_week.map((count, i) => (
              <div
                key={i}
                title={`${count} posts`}
                style={{
                  flex: 1,
                  background: C.accent,
                  borderRadius: "3px 3px 0 0",
                  height: count === 0 ? 2 : `${Math.max(6, (count / maxWeek) * 100)}%`,
                  // Older weeks fade back — recency is the through-line.
                  opacity: 0.35 + 0.65 * (i / stats.posts_per_week.length),
                }}
              />
            ))}
          </div>
        </div>

        <div style={card}>
          <div style={cardTitle}>Top cities</div>
          {stats.top_cities.map((c) => (
            <BarRow
              key={c.label}
              label={c.label}
              count={c.count}
              max={maxCity}
              color={C.accent}
            />
          ))}
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 40,
        }}
      >
        <div style={card}>
          <div style={cardTitle}>Interest frequency</div>
          {stats.interest_counts.map((c) => (
            <BarRow
              key={c.label}
              label={c.label}
              count={c.count}
              max={maxInterest}
              color={C.amber}
            />
          ))}
        </div>

        <div style={card}>
          <div style={cardTitle}>Age distribution</div>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 110 }}>
            {stats.age_buckets.map((b) => (
              <div
                key={b.label}
                style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 4,
                }}
                title={`${b.count} people`}
              >
                <div
                  style={{
                    width: "100%",
                    background: C.accent,
                    borderRadius: "4px 4px 0 0",
                    height: Math.max(4, (b.count / maxAge) * 90),
                  }}
                />
                <div style={{ fontSize: 10, color: C.faint }}>{b.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
