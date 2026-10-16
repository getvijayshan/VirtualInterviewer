"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./upload.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".docx"];

export default function UploadResumePage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    setError(null);
    if (picked) {
      const lower = picked.name.toLowerCase();
      if (!ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext))) {
        setFile(null);
        setError("Please choose a PDF or DOCX file.");
        return;
      }
      if (picked.size > MAX_BYTES) {
        setFile(null);
        setError("That file is over 10 MB. Please choose a smaller one.");
        return;
      }
    }
    setFile(picked);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/resumes`, { method: "POST", body: form });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ? JSON.stringify(body.detail) : `Upload failed (${res.status}).`);
      }
      const data = await res.json();
      // Parsing failures (needs_manual_entry) still land on the confirm screen,
      // where the candidate can fill the fields in by hand (FL-01.5).
      router.push(`/candidates/${data.candidate_id}/confirm`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploading(false);
    }
  }

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Step 1 of 6</p>
      <h1 className={styles.title}>Start with your resume</h1>
      <p className={styles.sub}>
        Upload a PDF or DOCX. We read it, you confirm the details, then you take one realistic
        interview and get a scorecard.
      </p>

      <label className={styles.drop}>
        <input
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          onChange={handleFileChange}
          disabled={uploading}
          className={styles.fileInput}
        />
        <span className={styles.dropText}>{file ? file.name : "Choose a resume file"}</span>
        <span className={styles.dropHint}>PDF or DOCX, up to 10 MB</span>
      </label>

      {error && <p className={styles.errorText}>{error}</p>}

      <button className={styles.uploadButton} onClick={handleUpload} disabled={!file || uploading}>
        {uploading ? "Reading your resume…" : "Upload and continue"}
      </button>
    </main>
  );
}
