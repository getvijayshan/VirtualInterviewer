"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import styles from "./interview.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ChatTurn = { role: "assistant" | "user"; content: string };

type InterviewTurnResponse = {
  question: string | null;
  turn_index: number | null;
  session_status: string;
  time_remaining_seconds: number;
  ended: boolean;
  answer_text: string | null;
};

type TranscriptResponse = {
  session_id: string;
  status: string;
  time_remaining_seconds: number;
  turns: { turn_index: number; role: "assistant" | "user"; content: string }[];
};

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function InterviewPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [ended, setEnded] = useState(false);
  const [chat, setChat] = useState<ChatTurn[]>([]);
  const [questionCount, setQuestionCount] = useState(0);
  const [timeRemaining, setTimeRemaining] = useState(0);

  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Initialize: resume an in-progress session, start a pending one, or show
  // the ended state — this is what makes a refresh/drop resumable (FL-05.7).
  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const sessionRes = await fetch(`${API_BASE}/sessions/${sessionId}`);
        if (!sessionRes.ok) throw new Error(`Could not load session (${sessionRes.status}).`);
        const session = await sessionRes.json();
        if (cancelled) return;

        if (session.status === "completed" || session.status === "abandoned") {
          setEnded(true);
          setLoading(false);
          return;
        }

        if (session.status === "in_progress") {
          const res = await fetch(`${API_BASE}/sessions/${sessionId}/transcript`);
          if (!res.ok) throw new Error(`Could not load transcript (${res.status}).`);
          const data: TranscriptResponse = await res.json();
          if (cancelled) return;
          setChat(data.turns.map((t) => ({ role: t.role, content: t.content })));
          setQuestionCount(data.turns.filter((t) => t.role === "assistant").length);
          setTimeRemaining(data.time_remaining_seconds);
        } else {
          const res = await fetch(`${API_BASE}/sessions/${sessionId}/start`, { method: "POST" });
          if (!res.ok) throw new Error(`Could not start the interview (${res.status}).`);
          const data: InterviewTurnResponse = await res.json();
          if (cancelled) return;
          if (data.question) setChat([{ role: "assistant", content: data.question }]);
          setQuestionCount(1);
          setTimeRemaining(data.time_remaining_seconds);
        }
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Failed to load session.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  async function startRecording() {
    setMicError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        void submitAnswer(new Blob(chunksRef.current, { type: "audio/webm" }));
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setMicError("Couldn't access your microphone — check browser permissions and try again.");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
    setProcessing(true);
  }

  async function submitAnswer(blob: Blob) {
    try {
      const formData = new FormData();
      formData.append("audio", blob, "answer.webm");
      const res = await fetch(`${API_BASE}/sessions/${sessionId}/turns`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ?? `Could not submit your answer (${res.status}).`);
      }
      const data: InterviewTurnResponse = await res.json();

      setChat((prev) => {
        const next = [...prev];
        if (data.answer_text) next.push({ role: "user", content: data.answer_text });
        if (data.question) next.push({ role: "assistant", content: data.question });
        return next;
      });
      setTimeRemaining(data.time_remaining_seconds);
      if (data.ended) {
        setEnded(true);
      } else {
        setQuestionCount((n) => n + 1);
      }
    } catch (err) {
      setMicError(err instanceof Error ? err.message : "Could not submit your answer.");
    } finally {
      setProcessing(false);
    }
  }

  async function handleEndEarly() {
    try {
      await fetch(`${API_BASE}/sessions/${sessionId}/end`, { method: "POST" });
    } finally {
      setEnded(true);
    }
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <p className={styles.statusText}>Loading your interview…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <main className={styles.page}>
        <p className={styles.statusTextError}>{loadError}</p>
      </main>
    );
  }

  if (ended) {
    return (
      <main className={styles.page}>
        <h1 className={styles.title}>Session complete.</h1>
        <p className={styles.statusText}>Your scorecard is being built in a follow-up release.</p>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <div className={styles.top}>
        <div className={styles.timer}>
          <span className={styles.ring} />
          {formatTime(timeRemaining)} left
        </div>
        <span className={styles.qCount}>Q{questionCount}</span>
      </div>

      <div className={styles.chat}>
        {chat.map((turn, i) => (
          <div key={i} className={`${styles.bubble} ${turn.role === "assistant" ? styles.bubbleQ : styles.bubbleA}`}>
            {turn.content}
          </div>
        ))}
        {processing && (
          <div className={`${styles.bubble} ${styles.bubbleQ} ${styles.typing}`}>
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      {micError && <p className={styles.statusTextError}>{micError}</p>}

      <div className={styles.micPanel}>
        <button
          type="button"
          className={`${styles.micButton} ${recording ? styles.micButtonRecording : ""}`}
          onClick={recording ? stopRecording : startRecording}
          disabled={processing}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
            <line x1="12" y1="18" x2="12" y2="22" />
          </svg>
        </button>
        <span className={`${styles.micLabel} ${recording ? styles.micLabelRecording : ""}`}>
          {processing ? "Transcribing…" : recording ? "Tap to stop" : "Tap to answer"}
        </span>
      </div>

      <div className={styles.endLink}>
        <button type="button" onClick={handleEndEarly}>
          End session early →
        </button>
      </div>
    </main>
  );
}
