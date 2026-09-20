# Candidate True Companion — Architecture & Design Decisions (Phase 1)

Living document. Source of truth for technical decisions made in planning discussions, ahead of any code being written. Pairs with `Candidate True Campanion.MD` (product vision) and `Feature-List-Phase1.md` (testable feature breakdown).

## 1. Phase 1 Scope

Smallest end-to-end slice of the product: resume upload → JD/role/topic input → single audio-answer interview → basic scorecard report. Chosen because it proves the whole "upload → interview → feedback" loop without committing to a virtual avatar, payments, or corporate mode up front. Everything else in the product vision layers on top without rework.

**Revised 2026-08-31/09-01**: interview answers are audio (candidate speaks, we transcribe), not typed text — see §4a. Target-role input also gained a third path, **Topic** (e.g. Data Structures, Algorithms, System Design, AI/ML), alongside JD-paste and role-pick, for candidates practicing a subject rather than a specific job.

Explicitly deferred: virtual avatar/video, corporate/B2B mode, screen-share + gesture/cognitive analysis, prep calendar, expert-led rounds, payments/top-up, live coding execution sandbox, company-specific prep, multi-tier packages, multiple interview modes (Grilling/Followup/Deepdive/Cry-for-help — Phase 1 ships one adaptive mode only).

## 2. Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js (React) | Fast to build forms/chat UI; clear upgrade path to add voice later |
| Backend | Python + FastAPI | LLM-heavy logic; Python's ecosystem is friendlier for resume parsing/NLP than Node |
| DB | Postgres | Candidates, sessions, transcripts, reports — relational fits the data shape |
| File storage | S3-compatible bucket | Raw resume files |
| LLM provider | Azure OpenAI (revised 2026-09-03, was Anthropic Claude API) | See §4 |
| Speech-to-text | Deepgram (initial) → Azure AI Foundry speech services (planned migration) | See §4a |
| LLM observability | Helicone (self-hosted, pinned to latest tagged stable release) | Per-session cost/usage tracking; see §5 |
| Hosting | Vercel (frontend) + self-managed VM, Dockerized Postgres (revised 2026-09-03, was Render/Fly.io) | See §10 |

Deliberately monolith-simple — no microservices, no message queue/worker infra (Celery/SQS) for Phase 1. Add only when parsing or report-generation latency becomes an actual bottleneck.

## 3. High-Level Flow

```
Resume upload → S3 → Parser (Claude, structured extraction) → Candidate profile in Postgres
Candidate confirms/edits profile → JD/role saved to session
Interview: backend orchestrates a stateful loop — sends system prompt (resume+JD+rules)
  + running transcript to Claude each turn → next question → streamed to frontend
  → all Q&A turns logged to Postgres as the transcript
OTP auth gate → full transcript sent to Claude (report-generation system prompt)
  → scorecard generated → stored → rendered
```

Key principle: **backend orchestrates the LLM, not the frontend.** Keeps prompts/API keys server-side, centralizes transcript logging, and lets interview logic change without a frontend deploy.

Session state lives in **Postgres, not in-memory** — a 30-minute interview must be resumable after a refresh/drop (FL-05.7). Duration/turn cap is enforced **server-side**, independent of what the model does (FL-05.5) — the model cannot be trusted alone to end a session on time.

## 4. Prompt Design

**System prompt** (frozen per session, cached):
- Interviewer persona/rules (one question at a time, adapt difficulty, don't reveal answers)
- Resume summary + JD/target role
- Output format instructions

**User/assistant turns**: standard multi-turn — each candidate answer as `user`, each generated question as `assistant`. Follow-up behavior is not a separate mechanism; it's the model reading the last answer in context. Explicit mode switches (if ever needed) go through a `system`-role message appended mid-conversation (Claude Opus 5 / Fable 5 support this without invalidating the cached prefix) rather than editing the top-level system prompt.

**Report generation** is a *separate* call at the end, over the full transcript, with a different ("strict grader") system prompt — not per-turn scoring.

**Implemented (2026-09-03, #10)**: `POST /sessions/{id}/report` / `GET /sessions/{id}/report` in `backend/app/routers/reports.py`. One tool-use call (`app/services/report_prompts.py`) over the whole transcript at once — per-question `strong`/`needs_work` + a specific note, an overall 0-10 score, and a communication summary. Idempotent: if a `Report` row already exists for the session, both endpoints return it without calling Claude again (FL-07.6) — no separate "regenerate" action exists yet. **Enforced server-side, not just at the frontend route**: both endpoints 403 unless `candidates.phone_verified_at` is set (FL-06) and 409 unless the session is `completed` — a direct API call can't skip the auth gate or grade a session still in progress. Resume-summary and target-description prompt fragments are shared with the interview loop via `app/services/candidate_context.py` (extracted from `interview_prompts.py` during this change) so the two don't drift independently.

**Implemented (2026-09-02, #7)**: `POST /sessions/{id}/start` / `POST /sessions/{id}/turns` / `GET /sessions/{id}/transcript` / `POST /sessions/{id}/end` in `backend/app/routers/interview.py`. System prompt built by `app/services/interview_prompts.py` from the candidate's resume + session target (jd/role/topic) — deterministic per session (FL-09.1: no session_id/timestamp interpolated into the text itself, those only go in the Helicone headers). Both the system prompt **and the last message of the growing conversation** are wrapped with an `ephemeral` cache breakpoint (`llm.cacheable()`) each call — caching only the system block would leave the resent transcript uncached; marking the last message lets Anthropic reuse the previous call's cached prefix, which is what actually delivers the "only pay full price for the new turn" saving described above. Real `cache_read_input_tokens > 0` verification still needs a live Anthropic key — not done in this environment.

The candidate's answer audio is transcribed via `app/services/transcription.py` before ever reaching Claude, then also uploaded to S3 (`transcript_turns.audio_file_url`) for STT-quality debugging. FL-05.5's hard stop is checked immediately after persisting the user's answer and before any further Claude call — time-based (`session.started_at + duration_min`), not turn-count-based. On a Claude failure mid-turn, the new user turn is rolled back (not committed) so the frontend can safely retry with the same recorded audio rather than leaving an orphaned answer with no follow-up question.

**Model choice**: a cheaper/faster deployment for the live interview loop (cost/latency balance); reserve the strongest available deployment for final report generation only (the one expensive call per session). Concretely which Azure OpenAI model deployment fills each role is the user's call once the Azure resource is provisioned — see §4c.

## 4c. LLM Provider Migration (Azure OpenAI)

**Decision (2026-09-03, user-directed) — IMPLEMENTED (2026-09-20)**: switched the LLM provider from Anthropic Claude to **Azure OpenAI**. Deepgram (§4a) is unaffected — this was LLM-only. Everything under §4 and §7 above describing the pre-migration Anthropic wiring (`anthropic_model_*` settings, `llm.cacheable()`, Anthropic response shapes) is superseded by this section.

`backend/app/services/llm.py` (#6) was rewritten from the Anthropic Messages API to the `openai` Python SDK's `AzureOpenAI` client:

- **Client**: `openai.AzureOpenAI(azure_endpoint=..., api_key=..., api_version=...)`. Azure identifies models by a **deployment name** you choose in the Azure portal, not a published model id — `settings.anthropic_model_*` became `settings.azure_openai_deployment_{extraction,interview,report}`, plus `azure_openai_endpoint`/`azure_openai_api_key`. `api_version` is **not** an env-configurable setting (2026-09-20, user-directed) — the openai SDK's `AzureOpenAI` client still requires the param internally, but it's fixed as `llm.AZURE_OPENAI_API_VERSION` in code rather than exposed per-environment, since there's no reason ops should need to tune it. Actual deployment names are the user's to set once the Azure resource is provisioned — **not yet filled in**, so the app still won't run against a real Azure OpenAI resource without that config.
- **Function calling**: rewritten to OpenAI's `tools: [{"type": "function", "function": {"name", "description", "parameters"}}]` / `tool_choice: {"type": "function", "function": {"name": ...}}` shape. Both `_RESUME_FIELDS_TOOL` in `llm.py` and `REPORT_TOOL` in `report_prompts.py` updated.
- **Response shape**: `response.choices[0].message.content` for plain text; `.tool_calls[*].function.arguments` is a **JSON string**, parsed with `json.loads()` in both `llm.extract_candidate_fields()` and `reports.py` (Anthropic's `block.input` was already a parsed dict — this is a real behavior difference, not just a rename).
- **Prompt caching**: Azure OpenAI/OpenAI caching is automatic for prompts over ~1024 tokens — no manual breakpoint markup. `llm.cacheable()` removed; `interview.py`'s `_messages_for_claude()` renamed `_build_messages()` and no longer wraps the last message. `llm.get_usage()` now reads `usage.prompt_tokens`/`usage.completion_tokens`/`usage.prompt_tokens_details.cached_tokens` — there's no Azure/OpenAI equivalent of Anthropic's separate "cache creation" cost, so `cache_creation_input_tokens` is hardcoded to 0 in the returned dict (kept only so callers don't need to branch on provider).
- **Errors**: `interview.py` and `reports.py` now catch `openai.OpenAIError` instead of `anthropic.APIError`.
- **Helicone**: `_build_client()` still passes `settings.helicone_base_url` as the client's `base_url` and forwards the same custom-property headers — **not verified against a real self-hosted Helicone Azure OpenAI integration**, since self-hosted Helicone's Azure OpenAI base-URL/header pattern reportedly differs from the Anthropic one already exercised. Treat Helicone routing as unverified until tested against a live Helicone instance with real Azure OpenAI traffic.
- **Tests**: `backend/tests/test_llm.py`, `test_interview_router.py`, `test_reports_router.py` rewritten to fake `openai.AzureOpenAI`/chat-completion response shapes instead of the Anthropic message/content-block shapes.
- **Not yet done**: no real Azure OpenAI resource has been exercised end-to-end (no endpoint/key/deployments available in this environment) — bundle that verification with **#14** rather than treating this migration as fully proven.

## 4a. Speech-to-Text (audio answers)

**Decision (2026-09-01)**: candidate answers are recorded as audio in the browser and transcribed server-side before being appended to the transcript as a `user` turn — the LLM only ever sees text.

- **Initial provider: Deepgram** (revised 2026-09-02, was Whisper). Hosted API, no self-managed model/GPU infra, low-latency streaming-capable transcription — a better fit than self-hosting Whisper for a small team that isn't running its own inference infrastructure yet.
- **Planned migration: Azure AI Foundry speech services.** Once available, swap the transcription call behind a single internal interface (e.g. `transcribe(audio_bytes) -> str`) so the migration is a provider-swap, not a rework of the interview loop.
- Track transcription latency and cost the same way as LLM calls — tag with `session_id` in Helicone (or log alongside it) so per-session cost includes STT, not just Claude usage.
- Recording UX: tap-to-record / tap-to-stop (not push-to-talk), waveform + elapsed-time feedback while recording, "Transcribing…" state before the answer appears in the transcript. See `design/` prototype for the reference interaction.

## 4b. Auth Gate (OTP)

**Implemented (2026-09-02, #9)**: `POST /auth/otp/request` / `POST /auth/otp/verify` in `backend/app/routers/auth.py`. A 6-digit code (hashed with SHA-256 before storage, compared with `hmac.compare_digest`), 5-minute TTL, single-use, capped at 5 verify attempts per code — the most recently requested code is the only one that's valid, so requesting a new one silently invalidates the last (FL-06.2/.3). Success sets `candidates.phone_verified_at` (FL-06.4); the interview screen redirects here the moment a session ends, before any report content renders (FL-06.1).

**Known gap**: no SMS provider is wired up yet — `app/services/otp.py`'s `send_otp()` just logs the code, and the request endpoint echoes it back as `debug_code` only when `APP_ENV=development`. Wiring a real provider (Twilio or similar) is real-credentials work, bundled with #14 rather than tracked separately.

## 4d. File Storage Migration (Azure Blob Storage)

**Decision (2026-09-20, user-directed) — IMPLEMENTED**: switched file storage from S3-compatible object storage to **Azure Blob Storage**, matching the rest of the stack now that Azure OpenAI (§4c) is in place.

`backend/app/services/storage.py` rewritten from `boto3`'s S3 client to `azure-storage-blob`'s `BlobServiceClient`:

- **Client**: `BlobServiceClient.from_connection_string(...)` → `get_container_client(container)` → `get_blob_client(blob_name).upload_blob(data, overwrite=True, content_settings=ContentSettings(content_type=...))`, returning `blob_client.url` as the stored URL. `settings.s3_bucket`/`s3_endpoint_url`/`aws_access_key_id`/`aws_secret_access_key` became `azure_storage_connection_string`/`azure_storage_container`.
- **Auth**: connection-string auth for now (the account's full connection string, account key included — simplest for local dev/testing). Revisit managed identity once the API is actually running on the VM (§10) — that would drop the connection string from `.env` entirely in favor of the VM's identity.
- Public interface unchanged: `upload_resume_file()` / `upload_interview_answer_audio()` still take the same args and return a stored URL string, so `resumes.py` and `interview.py` needed no changes beyond a docstring update.
- **Not yet verified**: container name not yet provided/created — code is written but unexercised against a live account. Bundle with #14.

## 5. Usage Tracking & Cost Control

- All Claude API calls proxied through **Helicone**, self-hosted (Docker), **pinned to the latest tagged stable release** — not `latest`/`main` — so upgrades are deliberate. (Helicone is Apache-2.0 OSS; as of this writing the company is in maintenance mode post-Mintlify acquisition — repo still active, self-hosting has no dependency risk, but re-evaluate Langfuse if development activity stalls further.)
- Every call tagged with `session_id` + call-type (`question_gen` / `report_gen`) via Helicone custom properties → per-session cost is queryable without building our own dashboard first.
- Prompt caching on the system prompt (resume+JD+rules) is the primary cost lever for multi-turn sessions — verify via `cache_read_input_tokens > 0` from turn 2 onward.
- 30-min free trial: don't pre-shrink it. Build usage tracking first, run real sessions, decide the SKU size from actual $/session data — trial abuse (repeat sign-ups) is a bigger cost risk than raw model spend, so rate-limit by device/email/OTP too.

**Implemented (2026-09-02, Anthropic-specific — superseded by §4c)**: `backend/app/services/llm.py` was the single entry point for every Claude call — `create_message(model, system, messages, max_tokens, call_type, session_id=None, tools=None, tool_choice=None)`, built against the Anthropic SDK pointed at `settings.helicone_base_url`, attaching `Helicone-Property-Call-Type` / `Helicone-Property-Session-Id` / `Helicone-Auth` headers. This `create_message`/`get_usage` interface and the Helicone tagging strategy carry over conceptually to the Azure OpenAI migration (§4c) — same call-type/session_id tagging — but the client construction, headers, and Helicone base-URL pattern for Azure OpenAI specifically still need to be implemented; self-hosted Helicone's OpenAI-family integration isn't the same wiring as its Anthropic one.

## 6. Database Schema (proposed, Phase 1)

```
candidates
  id (pk)
  name
  email
  phone
  phone_verified_at        -- set on successful OTP verify (FL-06.4)
  resume_file_url
  resume_parsed_json      -- structured extraction: skills, experience, education, projects
  created_at

otp_codes
  id (pk)
  candidate_id (fk -> candidates)
  phone                    -- number this code was sent to (may differ from candidates.phone if changed at the auth gate)
  code_hash                -- SHA-256, never the raw code
  expires_at
  consumed_at
  attempt_count
  created_at

sessions
  id (pk)
  candidate_id (fk -> candidates)
  target_type              -- 'jd' | 'role' | 'topic'
  jd_text                  -- set when target_type = 'jd'
  target_role               -- set when target_type = 'role'
  target_topic              -- set when target_type = 'topic' (e.g. 'data_structures', 'algorithms', 'system_design', 'ai_ml')
  duration_min              -- fixed 30 in Phase 1
  status                    -- pending | in_progress | completed | abandoned
  consent_at
  started_at
  ended_at

transcript_turns
  id (pk)
  session_id (fk -> sessions)
  turn_index               -- ordering
  role                     -- 'assistant' (question) | 'user' (answer)
  content                  -- transcribed text for user turns
  audio_file_url            -- nullable; raw answer audio in S3, kept for STT-quality debugging/reprocessing
  transcription_provider    -- 'deepgram' | 'azure_foundry' (nullable for assistant turns)
  created_at

reports
  id (pk)
  session_id (fk -> sessions, unique)
  scorecard_json            -- structured per-question scores
  feedback_text             -- communication/articulation notes
  generated_at

-- Usage is primarily tracked in Helicone (external), not duplicated in Postgres for Phase 1.
-- Revisit adding a local usage_logs table only if we need usage data joined into
-- in-app product queries (e.g. "candidates who used >$X") beyond what Helicone's
-- dashboard/API can answer directly.
```

Open question / to revisit: whether `resume_parsed_json` needs its own versioned table if candidates re-upload resumes across multiple sessions later (out of scope while B2C is single-session-per-candidate in Phase 1).

## 7. Decisions Explicitly Deferred

- Virtual avatar/video delivery, and TTS (spoken questions) — audio is candidate → system only in Phase 1; questions are still delivered as text
- Payment/billing integration for top-ups and paid tiers
- Corporate/B2B data model (separate from candidate-facing schema above)
- Coding-question execution sandbox
- Multi-agent or Managed Agents usage — Phase 1 uses direct Messages API calls only; no orchestration framework needed at this scale

## 8. Visual Identity

Three directions were mocked up and reviewed as an interactive prototype (`design/Candidate-True-Companion-Prototype.html`, theme picker built in): Signal (dark/indigo/violet, Space Grotesk + Inter), **Momentum** (warm cream/coral/gold, Bricolage Grotesque + Manrope), Clearance (crisp graphite/mint/lime, Archivo + IBM Plex).

**Decision (2026-09-01): Momentum** — warm, coach-like, energetic; matches the "energetic but serious" brief for a Gen Z/Millennial audience better than the more clinical/tech-forward Signal or Clearance. Set via `ACTIVE_BRAND` in `frontend/app/layout.tsx`. Token values for all three remain in `frontend/theme/tokens.css` — kept live (not deleted) in case of a future pivot, but Momentum is what ships.

## 9. Repository & Branching

Repo: `https://github.com/getvijayshan/VirtualInterviewer`. **Git-flow** branching: `main` (release-only, always deployable), `develop` (integration branch), `feature/*` branched from and merged back into `develop`, `release/*` and `hotfix/*` as needed off `main`/`develop` per standard git-flow.

## 10. Deployment (Backend)

**Decision (2026-09-03, user-directed, NOT YET IMPLEMENTED)**: backend (API + database) moves off the originally-proposed Render/Fly.io to a **self-managed VM**:

- **Postgres runs in Docker** on the VM, with its data directory **bind-mounted to a host path** (not an anonymous/named Docker volume) so the data survives a container recreate independent of Docker's own volume lifecycle. `DATABASE_URL` in `.env` then points at that container (`localhost:5432` if the port is published to the host).
- **The FastAPI API runs directly on the VM** (not containerized) — e.g. a `venv` + a process manager (systemd unit, or similar) running `uvicorn app.main:app`. This is a deliberate split: dockerize the stateful piece (DB), keep the stateless app process simple to redeploy (`git pull` + restart) without also managing an image build/push step for every code change. Revisit if the app process itself needs container-level isolation or the deploy story gets more complex.
- Frontend hosting (Vercel) is unaffected — this decision is backend-only.
- No infra-as-code (Terraform/Ansible) yet — a `docker-compose.yml` for Postgres plus manual VM setup is enough for Phase 1 traffic. Revisit if there's ever a second VM or the manual setup steps stop being reproducible from memory.

`infra/docker-compose.yml` (Postgres only) is scaffolded. Not yet implemented: actual VM provisioning and the systemd unit for the API process — those need the real VM to exist first.
