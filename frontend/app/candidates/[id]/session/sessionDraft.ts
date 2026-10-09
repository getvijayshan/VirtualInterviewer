// Transient client-side state passed from the target-selection screen (FL-03)
// to the consent screen (FL-04) — both post to the same POST /sessions call,
// but are two separate routes/screens per the reference prototype. Not meant
// to survive a full page reload from scratch; sessionStorage is enough.

export type TargetDraft = {
  target_type: "jd" | "role" | "topic" | null;
  jd_text: string;
  target_role: string;
  target_topic: string;
};

function key(candidateId: string): string {
  return `ctc-session-draft-${candidateId}`;
}

export function emptyDraft(): TargetDraft {
  return { target_type: null, jd_text: "", target_role: "", target_topic: "" };
}

export function loadDraft(candidateId: string): TargetDraft {
  if (typeof window === "undefined") return emptyDraft();
  try {
    const raw = window.sessionStorage.getItem(key(candidateId));
    if (!raw) return emptyDraft();
    return { ...emptyDraft(), ...JSON.parse(raw) };
  } catch {
    return emptyDraft();
  }
}

export function saveDraft(candidateId: string, draft: TargetDraft): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(key(candidateId), JSON.stringify(draft));
  } catch {
    // sessionStorage unavailable (private mode, etc.) — draft just won't carry over
  }
}

export function clearDraft(candidateId: string): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(key(candidateId));
  } catch {
    // ignore
  }
}
