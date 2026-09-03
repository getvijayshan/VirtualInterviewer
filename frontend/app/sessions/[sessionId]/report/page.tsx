"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "./report.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type QuestionFeedback = {
  question: string;
  quality: "strong" | "needs_work";
  note: string;
};

type ReportData = {
  overall_score: number;
  questions: QuestionFeedback[];
  communication_notes: string;
};

export default function ReportPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [report, setReport] = useState<ReportData | null>(null);
  const [loadingLabel, setLoadingLabel] = useState("Loading your report…");
  const [error, setError] = useState<string | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const getRes = await fetch(`${API_BASE}/sessions/${sessionId}/report`);
        if (getRes.ok) {
          if (!cancelled) setReport(await getRes.json());
          return;
        }
        if (getRes.status === 403) {
          if (!cancelled) router.replace(`/sessions/${sessionId}/auth`);
          return;
        }
        if (getRes.status !== 404) {
          throw new Error(`Could not load report (${getRes.status}).`);
        }

        // Not generated yet — request it. This is the one LLM call in this
        // flow, so it can take a few seconds.
        if (!cancelled) setLoadingLabel("Grading your interview — this can take a few seconds…");
        const postRes = await fetch(`${API_BASE}/sessions/${sessionId}/report`, { method: "POST" });
        if (postRes.status === 403) {
          if (!cancelled) router.replace(`/sessions/${sessionId}/auth`);
          return;
        }
        if (!postRes.ok) {
          const body = await postRes.json().catch(() => null);
          throw new Error(body?.detail ?? `Could not generate report (${postRes.status}).`);
        }
        if (!cancelled) setReport(await postRes.json());
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load report.");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [sessionId, router]);

  if (error) {
    return (
      <main className={styles.page}>
        <p className={styles.statusTextError}>{error}</p>
      </main>
    );
  }

  if (!report) {
    return (
      <main className={styles.page}>
        <p className={styles.statusText}>{loadingLabel}</p>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Step 6 of 6</p>
      <h1 className={styles.title}>Your scorecard</h1>
      <p className={styles.sub}>Based on your full interview session.</p>

      <div className={styles.scoreHero}>
        <div className={styles.scoreNum}>
          {report.overall_score.toFixed(1)}
          <small>/10</small>
        </div>
        <div className={styles.scoreLabel}>Overall performance</div>
      </div>

      {report.questions.map((q, i) => (
        <div
          key={i}
          className={`${styles.reportItem} ${openIndex === i ? styles.reportItemOpen : ""}`}
          onClick={() => setOpenIndex(openIndex === i ? null : i)}
        >
          <span className={`${styles.tag} ${q.quality === "strong" ? styles.tagStrong : styles.tagWork}`}>
            {q.quality === "strong" ? "Strong" : "Needs work"}
          </span>
          <div className={styles.reportQuestion}>&quot;{q.question}&quot;</div>
          <div className={styles.reportNote}>{q.note}</div>
          <div className={styles.toggleHint}>{openIndex === i ? "tap to collapse" : "tap to expand"}</div>
        </div>
      ))}

      <div className={styles.commCard}>
        <p className={styles.commLabel}>Communication</p>
        <p className={styles.commText}>{report.communication_notes}</p>
      </div>
    </main>
  );
}
