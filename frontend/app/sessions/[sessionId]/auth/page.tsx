"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "./auth.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Step = "loading" | "phone" | "code" | "error";

export default function AuthGatePage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [step, setStep] = useState<Step>("loading");
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/sessions/${sessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Could not load session (${res.status}).`);
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        setCandidateId(data.candidate_id);
        setStep("phone");
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Failed to load session.");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function handleSendCode() {
    if (!candidateId || !phone.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, phone: phone.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Could not send code (${res.status}).`);
      }
      setCode("");
      setStep("code");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not send code.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify() {
    if (!candidateId || !code.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/otp/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, code: code.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        // FL-06.3: incorrect/expired code shows a clear retry path
        throw new Error(body?.detail ?? `Verification failed (${res.status}).`);
      }
      router.push(`/sessions/${sessionId}/report`);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Verification failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (step === "loading") {
    return (
      <main className={styles.page}>
        <p className={styles.statusText}>Loading…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <main className={styles.page}>
        <p className={styles.errorText}>{loadError}</p>
      </main>
    );
  }

  if (step === "phone") {
    return (
      <main className={styles.page}>
        <p className={styles.eyebrow}>One more step</p>
        <h1 className={styles.title}>Verify it&apos;s you</h1>
        <p className={styles.sub}>We&apos;ll text you a 6-digit code before showing your results.</p>

        {formError && <p className={styles.errorText}>{formError}</p>}

        <div className={styles.field}>
          <input
            className={styles.input}
            style={{ textAlign: "left", fontFamily: "var(--font-sans)", letterSpacing: "normal" }}
            type="tel"
            placeholder="Phone number"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>

        <button
          type="button"
          className={styles.primaryButton}
          onClick={handleSendCode}
          disabled={submitting || !phone.trim()}
        >
          {submitting ? "Sending…" : "Send code"}
        </button>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>One more step</p>
      <h1 className={styles.title}>Enter your code</h1>
      <p className={styles.sub}>We sent a 6-digit code to {phone}.</p>

      {formError && <p className={styles.errorText}>{formError}</p>}

      <div className={styles.field}>
        <input
          className={styles.input}
          inputMode="numeric"
          maxLength={6}
          placeholder="••••••"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
        />
      </div>

      <button type="button" className={styles.primaryButton} onClick={handleVerify} disabled={submitting || code.length !== 6}>
        {submitting ? "Verifying…" : "Verify"}
      </button>

      <p className={styles.hint}>Code expires in 5 minutes.</p>

      <div className={styles.secondaryLink}>
        <button type="button" onClick={() => setStep("phone")}>
          Didn&apos;t get it? Request a new code
        </button>
      </div>
    </main>
  );
}
