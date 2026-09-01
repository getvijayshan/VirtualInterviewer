# Candidate True Companion — Phase 1 Feature List

Scope: B2C Individual Mode, text-chat interview only (no avatar/voice yet), single interview mode, Basic tier report only. See `Candidate True Campanion.MD` for full product vision and `Architecture-Decisions.md` for technical design.

Each feature has an ID (for traceability into future automated test suites), a short description, and acceptance criteria.

---

## FL-01 — Resume Upload & Parsing
**Description:** Candidate uploads a resume file; system extracts structured data.
- FL-01.1: Accepts PDF and DOCX formats
- FL-01.2: Rejects unsupported file types with a clear error message
- FL-01.3: Rejects files above max size limit (define limit, e.g. 5MB)
- FL-01.4: Extracts name, contact info, skills, work experience, projects, education
- FL-01.5: Parsing failure (corrupt/unreadable file) surfaces a retry/manual-entry path, not a silent crash
- FL-01.6: Extracted data is persisted against a candidate record before confirmation

## FL-02 — Resume Confirmation Screen
**Description:** Candidate reviews and corrects extracted resume data.
- FL-02.1: All extracted fields are editable
- FL-02.2: Candidate can add missing fields (e.g. skill not detected)
- FL-02.3: Saving confirmation updates the stored candidate profile
- FL-02.4: Empty/invalid required fields block progression with inline validation

## FL-03 — Target Role Input
**Description:** Candidate provides a Job Description or selects a target role.
- FL-03.1: Candidate can paste free-text JD
- FL-03.2: Candidate can instead select a designation/role from a predefined list (fallback when no JD)
- FL-03.3: At least one of JD or role selection is required to proceed
- FL-03.4: JD/role is persisted against the session record

## FL-04 — Consent & Session Setup
**Description:** Candidate consents to data use and configures the interview session.
- FL-04.1: Consent checkbox/screen must be explicitly accepted before proceeding
- FL-04.2: Duration selector defaults to 30 minutes
- FL-04.3: (Phase 1: duration is fixed at 30 min — top-up/payment deferred to a later phase)
- FL-04.4: Declining consent halts the flow with no session created

## FL-05 — Interview Session (Core Loop)
**Description:** Text-based adaptive interview between candidate and AI interviewer.
- FL-05.1: Session opens with an introductory message and first question
- FL-05.2: Questions adapt based on resume experience level and JD/role (not a static script)
- FL-05.3: Question mix includes theory, scenario-based, and project-experience-based questions
- FL-05.4: Each candidate answer is persisted to the transcript in order
- FL-05.5: Session enforces the configured duration as a hard server-side cutoff, independent of model behavior
- FL-05.6: Candidate can end the session early
- FL-05.7: A dropped/refreshed session is resumable from the last saved turn (state lives in DB, not in-memory)
- FL-05.8: Full transcript (question + answer pairs, in order) is retrievable after the session ends

## FL-06 — Authentication Gate
**Description:** Candidate authenticates via email/OTP before results are shown.
- FL-06.1: Auth prompt appears immediately after interview completion, before any report content
- FL-06.2: OTP is time-limited and single-use
- FL-06.3: Incorrect/expired OTP shows a clear retry path
- FL-06.4: Successful auth links the session to a persistent candidate account

## FL-07 — Report Generation & Display (Basic Tier)
**Description:** Post-interview scorecard generated from the full transcript.
- FL-07.1: Report includes per-question correctness/quality assessment
- FL-07.2: Report includes a suggested improved answer per question
- FL-07.3: Report includes overall communication/articulation notes
- FL-07.4: Report includes an overall scorecard/summary
- FL-07.5: Report generation is a single LLM call over the full transcript (not per-turn scoring)
- FL-07.6: Report is persisted and re-viewable without regenerating

## FL-08 — LLM Usage Tracking & Cost Observability
**Description:** Every model call is tracked and attributable to a session.
- FL-08.1: All Claude API calls are routed through Helicone (self-hosted, pinned to a tagged stable release — not `latest`/`main`)
- FL-08.2: Every call is tagged with `session_id` and call-type (`question_gen` / `report_gen`) via custom properties
- FL-08.3: Per-session token usage (input/output/cache read/cache write) is queryable
- FL-08.4: Per-session cost is queryable/derivable
- FL-08.5: A trial session that exceeds its time/turn cap stops issuing new model calls (hard stop, see FL-05.5)

## FL-09 — Prompt Caching
**Description:** System prompt (resume + JD + instructions) is cached to reduce cost on multi-turn sessions.
- FL-09.1: System prompt content is stable/deterministic across turns within a session (no timestamps/session IDs interpolated into it)
- FL-09.2: `cache_read_input_tokens` > 0 is observed from the second turn onward in a session (cache is actually hitting)

---

## Out of scope for Phase 1 (tracked for later feature lists)
Corporate/B2B mode, virtual avatar/voice, screen-share + gesture/cognitive analysis, prep calendar, expert-led live rounds, payments/top-up, coding-execution sandbox, company-specific prep, multi-round packages (Advance/Premium tiers), interview mode variants (Grilling/Followup/Deepdive/Cry-for-help).
