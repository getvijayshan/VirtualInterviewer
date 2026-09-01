export default function Home() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100%",
        padding: 24,
        textAlign: "center",
        gap: 12,
      }}
    >
      <p
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          color: "var(--text-faint)",
        }}
      >
        Candidate True Companion
      </p>
      <h1 style={{ fontFamily: "var(--font-display)", fontSize: 28, margin: 0 }}>
        Scaffold running.
      </h1>
      <p style={{ color: "var(--text-soft)", maxWidth: 420, margin: 0 }}>
        Resume upload → confirm → role/JD/topic → consent → interview → scorecard
        screens land here as each is built. See{" "}
        <code>docs/Feature-List-Phase1.md</code> for the build order.
      </p>
    </main>
  );
}
