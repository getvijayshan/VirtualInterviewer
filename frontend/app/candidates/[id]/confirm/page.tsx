"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import styles from "./confirm.module.css";

type ExperienceEntry = {
  company: string;
  role: string;
  start_date?: string;
  end_date?: string;
  summary?: string;
};

type EducationEntry = {
  institution: string;
  degree?: string;
  year?: string;
};

type ProjectEntry = {
  name: string;
  summary?: string;
};

type ParsedFields = {
  skills?: string[];
  experience?: ExperienceEntry[];
  education?: EducationEntry[];
  projects?: ProjectEntry[];
};

type Candidate = {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  resume_file_url: string | null;
  resume_parsed_json: ParsedFields | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ConfirmResumePage() {
  const params = useParams<{ id: string }>();
  const candidateId = params.id;

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [newSkill, setNewSkill] = useState("");
  const [experience, setExperience] = useState<ExperienceEntry[]>([]);
  const [education, setEducation] = useState<EducationEntry[]>([]);
  const [projects, setProjects] = useState<ProjectEntry[]>([]);

  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${API_BASE}/resumes/${candidateId}`);
        if (!res.ok) throw new Error(`Could not load candidate (${res.status}).`);
        const data: Candidate = await res.json();
        if (cancelled) return;
        setName(data.name ?? "");
        setEmail(data.email ?? "");
        setPhone(data.phone ?? "");
        setSkills(data.resume_parsed_json?.skills ?? []);
        setExperience(data.resume_parsed_json?.experience ?? []);
        setEducation(data.resume_parsed_json?.education ?? []);
        setProjects(data.resume_parsed_json?.projects ?? []);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "Failed to load candidate.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [candidateId]);

  // FL-02.4: inline validation — required fields block progression
  const nameError = touched && !name.trim() ? "Name is required." : null;
  const emailError = touched && !EMAIL_PATTERN.test(email) ? "Enter a valid email address." : null;
  const isValid = name.trim().length > 0 && EMAIL_PATTERN.test(email);

  function addSkill() {
    const value = newSkill.trim();
    if (!value || skills.includes(value)) return;
    setSkills([...skills, value]);
    setNewSkill("");
  }

  function removeSkill(skill: string) {
    setSkills(skills.filter((s) => s !== skill));
  }

  function updateExperience(index: number, patch: Partial<ExperienceEntry>) {
    setExperience(experience.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  }

  function updateEducation(index: number, patch: Partial<EducationEntry>) {
    setEducation(education.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  }

  function updateProject(index: number, patch: Partial<ProjectEntry>) {
    setProjects(projects.map((p, i) => (i === index ? { ...p, ...patch } : p)));
  }

  async function handleSave() {
    setTouched(true);
    if (!isValid) return;

    setSaving(true);
    setSaveError(null);
    try {
      const res = await fetch(`${API_BASE}/resumes/${candidateId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          phone: phone.trim() || null,
          skills,
          experience: experience.filter((e) => e.company.trim() && e.role.trim()),
          education: education.filter((e) => e.institution.trim()),
          projects: projects.filter((p) => p.name.trim()),
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail ? JSON.stringify(body.detail) : `Save failed (${res.status}).`);
      }
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <p className={styles.statusText}>Loading your resume details…</p>
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

  return (
    <main className={styles.page}>
      <p className={styles.eyebrow}>Step 2 of 6</p>
      <h1 className={styles.title}>Confirm your details</h1>
      <p className={styles.sub}>Everything here came from your resume — fix anything we got wrong.</p>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="name">
          Name
        </label>
        <input
          id="name"
          className={`${styles.input} ${nameError ? styles.inputError : ""}`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => setTouched(true)}
        />
        {nameError && <p className={styles.errorText}>{nameError}</p>}
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          className={`${styles.input} ${emailError ? styles.inputError : ""}`}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => setTouched(true)}
        />
        {emailError && <p className={styles.errorText}>{emailError}</p>}
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="phone">
          Phone
        </label>
        <input id="phone" className={styles.input} value={phone} onChange={(e) => setPhone(e.target.value)} />
      </div>

      <div className={styles.field}>
        <span className={styles.label}>Skills</span>
        <div className={styles.chips}>
          {skills.map((skill) => (
            <span key={skill} className={styles.chip}>
              {skill}
              <button type="button" onClick={() => removeSkill(skill)} aria-label={`Remove ${skill}`}>
                ✕
              </button>
            </span>
          ))}
          <input
            className={styles.chipInput}
            placeholder="+ Add a skill"
            value={newSkill}
            onChange={(e) => setNewSkill(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addSkill();
              }
            }}
            onBlur={addSkill}
          />
        </div>
      </div>

      <div className={styles.field}>
        <span className={styles.label}>Experience</span>
        {experience.map((entry, i) => (
          <div key={i} className={styles.entryCard}>
            <div className={styles.entryRow}>
              <input
                className={styles.input}
                placeholder="Company"
                value={entry.company}
                onChange={(e) => updateExperience(i, { company: e.target.value })}
              />
              <input
                className={styles.input}
                placeholder="Role"
                value={entry.role}
                onChange={(e) => updateExperience(i, { role: e.target.value })}
              />
            </div>
            <div className={styles.entryRow}>
              <input
                className={styles.input}
                placeholder="Start date"
                value={entry.start_date ?? ""}
                onChange={(e) => updateExperience(i, { start_date: e.target.value })}
              />
              <input
                className={styles.input}
                placeholder="End date"
                value={entry.end_date ?? ""}
                onChange={(e) => updateExperience(i, { end_date: e.target.value })}
              />
            </div>
            <div className={styles.removeRow}>
              <button
                type="button"
                className={styles.removeButton}
                onClick={() => setExperience(experience.filter((_, idx) => idx !== i))}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        <button
          type="button"
          className={styles.addButton}
          onClick={() => setExperience([...experience, { company: "", role: "" }])}
        >
          + Add experience
        </button>
      </div>

      <div className={styles.field}>
        <span className={styles.label}>Education</span>
        {education.map((entry, i) => (
          <div key={i} className={styles.entryCard}>
            <div className={styles.entryRow}>
              <input
                className={styles.input}
                placeholder="Institution"
                value={entry.institution}
                onChange={(e) => updateEducation(i, { institution: e.target.value })}
              />
              <input
                className={styles.input}
                placeholder="Degree"
                value={entry.degree ?? ""}
                onChange={(e) => updateEducation(i, { degree: e.target.value })}
              />
            </div>
            <div className={styles.removeRow}>
              <button
                type="button"
                className={styles.removeButton}
                onClick={() => setEducation(education.filter((_, idx) => idx !== i))}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        <button
          type="button"
          className={styles.addButton}
          onClick={() => setEducation([...education, { institution: "" }])}
        >
          + Add education
        </button>
      </div>

      <div className={styles.field}>
        <span className={styles.label}>Projects</span>
        {projects.map((entry, i) => (
          <div key={i} className={styles.entryCard}>
            <input
              className={styles.input}
              placeholder="Project name"
              value={entry.name}
              onChange={(e) => updateProject(i, { name: e.target.value })}
            />
            <div className={styles.removeRow}>
              <button
                type="button"
                className={styles.removeButton}
                onClick={() => setProjects(projects.filter((_, idx) => idx !== i))}
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        <button type="button" className={styles.addButton} onClick={() => setProjects([...projects, { name: "" }])}>
          + Add project
        </button>
      </div>

      <div className={styles.actions}>
        {saveError && <p className={styles.statusTextError}>{saveError}</p>}
        {saved ? (
          <p className={styles.statusText}>Saved. Next: target role (coming soon).</p>
        ) : (
          <button className={styles.saveButton} onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Looks good, continue"}
          </button>
        )}
      </div>
    </main>
  );
}
