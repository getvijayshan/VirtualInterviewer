"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "../session.module.css";
import { clearDraft, loadDraft, type TargetDraft } from "../sessionDraft";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function summarize(draft: TargetDraft): { label: string; text: string } {
  if (draft.target_type === "jd") return { label: "Job description", text: draft.jd_text };
  if (draft.target_type === "role") return { label: "Target role", text: draft.target_role };
  if (draft.target_type === "topic") return { label: "Topic", text: draft.target_topic };
  return { label: "Target", text: "" };
}

export default function ConsentPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const candidateId = params.id;

  const [draft, setDraft] = useState<TargetDraft | null>(null);
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    const loaded = loadDraft(candidateId);
    if (!loaded.target_type) {
      // FL-03.3: no target selected yet — send the candidate back to pick one
      router.replace(`/candidates/${candidateId}/session/target`);
      return;
    }
    setDraft(loaded);
  }, [candidateId, router]);

  async function handleStart() {
    if (!consent || !draft) return; // FL-04.4: no session is created without consent
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: candidateId,
          target_type: draft.target_type,
          jd_text: draft.target_type === "jd" ? draft.jd_text : undefined,
          target_role: draft.target_type === "role" ? draft.target_role : undefined,
          target_topic: draft.target_type === "topic" ? draft.target_topic : undefined,
          consent: true,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ? JSON.stringify(body.detail) : `Could not start session (${res.status}).`);
      }
      const data = await res.json();
      clearDraft(candidateId);
      router.push(`/sessions/${data.id}/interview`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not start session.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!draft) {
    return (
      <main className={styles.page}>
        <p className={styles.statusText}>Loading…</p>
      </main>
    );
  }

  const summary = summarize(draft);

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Step 4 of 6</p>
      <h1 className={styles.title}>Before we begin</h1>
      <p className={styles.sub}>Quick check, then we&apos;ll start your session.</p>

      <div className={styles.summaryCard}>
        <p className={styles.summaryLabel}>{summary.label}</p>
        <p className={styles.summaryText}>{summary.text}</p>
      </div>

      <div className={styles.consentBox} onClick={() => setConsent(!consent)}>
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <p>I agree to have my resume and interview responses used to generate my feedback report.</p>
      </div>

      <div className={styles.durationPill}>
        <div>
          <span className={styles.durationLabel}>Session length</span>
          <span className={styles.durationFixedTag}>FIXED FOR NOW</span>
        </div>
        <span className={styles.durationValue}>30:00 min</span>
      </div>

      {submitError && <p className={styles.statusTextError}>{submitError}</p>}

      <button type="button" className={styles.primaryButton} onClick={handleStart} disabled={!consent || submitting}>
        {submitting ? "Starting…" : "Start interview"}
      </button>
    </main>
  );
}
