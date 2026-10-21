"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "./auth.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Step = "loading" | "choose" | "code";

const PROVIDER_LABELS: Record<string, string> = { google: "Google", linkedin: "LinkedIn" };

export default function AuthGatePage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [step, setStep] = useState<Step>("loading");
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [providers, setProviders] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [testCode, setTestCode] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/sessions/${sessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Could not load session (${res.status}).`);
        return res.json();
      })
      .then(async (data) => {
        // Prefill from the resume, and learn which OAuth buttons are enabled.
        const [candidate, methods] = await Promise.all([
          fetch(`${API_BASE}/resumes/${data.candidate_id}`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
          fetch(`${API_BASE}/auth/methods`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
        ]);
        if (cancelled) return;
        setCandidateId(data.candidate_id);
        setEmail(candidate?.email ?? "");
        setProviders(methods?.oauth_providers ?? []);
        // The OAuth callback sends failures back here as ?error=...
        const oauthError = new URLSearchParams(window.location.search).get("error");
        if (oauthError) setFormError(oauthError);
        setStep("choose");
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Failed to load session.");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function handleSendCode() {
    if (!candidateId || !email.trim()) return;
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_id: candidateId, email: email.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Could not send code (${res.status}).`);
      }
      const sent = await res.json().catch(() => null);
      setTestCode(sent?.debug_code ?? null);
      setCode("");
      setStep("code");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not send code.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleOAuth(provider: string) {
    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(`${API_BASE}/auth/oauth/${provider}/start?session_id=${sessionId}`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Could not start sign-in (${res.status}).`);
      }
      const { authorize_url } = await res.json();
      window.location.href = authorize_url;
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not start sign-in.");
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

  if (step === "choose") {
    return (
      <main className={styles.page}>
        <p className={styles.eyebrow}>One more step</p>
        <h1 className={styles.title}>Verify it&apos;s you</h1>
        <p className={styles.sub}>Sign in to see your results.</p>

        {formError && <p className={styles.errorText}>{formError}</p>}

        {providers.map((p) => (
          <button
            key={p}
            type="button"
            className={styles.oauthButton}
            onClick={() => handleOAuth(p)}
            disabled={submitting}
          >
            Continue with {PROVIDER_LABELS[p] ?? p}
          </button>
        ))}

        {providers.length > 0 && <p className={styles.divider}>or use your email</p>}

        <div className={styles.field}>
          <input
            className={styles.input}
            style={{ textAlign: "left", fontFamily: "var(--font-sans)", letterSpacing: "normal" }}
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <button
          type="button"
          className={styles.primaryButton}
          onClick={handleSendCode}
          disabled={submitting || !email.trim()}
        >
          {submitting ? "Sending…" : "Email me a code"}
        </button>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>One more step</p>
      <h1 className={styles.title}>Enter your code</h1>
      <p className={styles.sub}>We emailed a 6-digit code to {email}.</p>
      {testCode && <p className={styles.hint}>Test mode: your code is {testCode}</p>}

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
        <button type="button" onClick={() => setStep("choose")}>
          Didn&apos;t get it? Request a new code
        </button>
      </div>
    </main>
  );
}
