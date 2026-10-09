"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "../session.module.css";
import { loadDraft, saveDraft, type TargetDraft } from "../sessionDraft";

type TargetOptions = {
  roles: string[];
  topics: { value: string; label: string }[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Tab = "jd" | "role" | "topic";

export default function TargetSelectionPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const candidateId = params.id;

  const [options, setOptions] = useState<TargetOptions | null>(null);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [tab, setTab] = useState<Tab>("jd");
  const [jdText, setJdText] = useState("");
  const [selectedRole, setSelectedRole] = useState("");
  const [selectedTopic, setSelectedTopic] = useState("");
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    const draft = loadDraft(candidateId);
    if (draft.target_type) setTab(draft.target_type);
    setJdText(draft.jd_text);
    setSelectedRole(draft.target_role);
    setSelectedTopic(draft.target_topic);
  }, [candidateId]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/sessions/target-options`)
      .then((res) => {
        if (!res.ok) throw new Error(`Could not load options (${res.status}).`);
        return res.json();
      })
      .then((data: TargetOptions) => {
        if (!cancelled) setOptions(data);
      })
      .catch((err) => {
        if (!cancelled) setOptionsError(err instanceof Error ? err.message : "Failed to load options.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // FL-03.3: at least one of JD/role/topic is required to proceed
  const isValid =
    (tab === "jd" && jdText.trim().length > 0) ||
    (tab === "role" && selectedRole.length > 0) ||
    (tab === "topic" && selectedTopic.length > 0);

  function handleContinue() {
    setTouched(true);
    if (!isValid) return;
    const draft: TargetDraft = {
      target_type: tab,
      jd_text: jdText,
      target_role: selectedRole,
      target_topic: selectedTopic,
    };
    saveDraft(candidateId, draft);
    router.push(`/candidates/${candidateId}/session/consent`);
  }

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Step 3 of 6</p>
      <h1 className={styles.title}>What do you want to be interviewed on?</h1>
      <p className={styles.sub}>Paste a JD, pick a role, or drill into one topic.</p>

      <div className={styles.segmented}>
        <button type="button" className={tab === "jd" ? styles.on : ""} onClick={() => setTab("jd")}>
          Paste JD
        </button>
        <button type="button" className={tab === "role" ? styles.on : ""} onClick={() => setTab("role")}>
          Pick a role
        </button>
        <button type="button" className={tab === "topic" ? styles.on : ""} onClick={() => setTab("topic")}>
          Topic
        </button>
      </div>

      {optionsError && <p className={styles.statusTextError}>{optionsError}</p>}

      {tab === "jd" && (
        <textarea
          className={styles.textarea}
          placeholder="Paste the job description here…"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
        />
      )}

      {tab === "role" && (
        <div className={styles.optionList}>
          {(options?.roles ?? []).map((role) => (
            <button
              key={role}
              type="button"
              className={`${styles.optionItem} ${selectedRole === role ? styles.on : ""}`}
              onClick={() => setSelectedRole(role)}
            >
              {role}
            </button>
          ))}
        </div>
      )}

      {tab === "topic" && (
        <div className={styles.optionList}>
          {(options?.topics ?? []).map((topic) => (
            <button
              key={topic.value}
              type="button"
              className={`${styles.optionItem} ${selectedTopic === topic.value ? styles.on : ""}`}
              onClick={() => setSelectedTopic(topic.value)}
            >
              {topic.label}
            </button>
          ))}
        </div>
      )}

      {touched && !isValid && (
        <p className={styles.errorText}>
          {tab === "jd" ? "Paste a job description to continue." : "Pick one to continue."}
        </p>
      )}

      <button type="button" className={styles.primaryButton} onClick={handleContinue}>
        Continue
      </button>
    </main>
  );
}
