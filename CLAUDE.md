# CLAUDE.md

Guidance for Claude Code (and any other agent) working in this repo.

## What this is

**Candidate True Companion** — an AI interview-prep platform. Phase 1 MVP: resume upload → confirm → target role/JD/topic → consent → one audio-answer interview → scorecard report. Full product vision, current scope, and every technical decision made so far live in `docs/` — read `docs/Architecture-Decisions.md` before making architectural changes, it is the living source of truth.

## Repo layout

```
frontend/          Next.js (React) app
backend/           FastAPI app
frontend/theme/tokens.css   Brand theme tokens (3 directions, see below)
docs/              ADR + product/feature docs (kept updated; no other docs written yet by design)
design/            Shareable HTML prototypes (not shipped code)
```

## Stack

Next.js frontend, Python/FastAPI backend, Postgres, S3-compatible file storage, Anthropic Claude API (Sonnet for the interview loop, Opus for report generation) routed through self-hosted Helicone for usage tracking, Whisper for speech-to-text (planned migration to Azure AI Foundry — keep STT behind a single `transcribe()` interface so that swap stays a provider change, not a rework). Monolith-simple: no microservices, no queue infra until an actual bottleneck shows up.

## Conventions

- **Theming**: never hardcode a brand color, gradient, or font name in a component. Everything reads from the CSS custom properties in `frontend/theme/tokens.css` (`var(--primary)`, `var(--font-display)`, etc.). The shipped direction is set in one place (`ACTIVE_BRAND` in `frontend/app/layout.tsx`) — no direction is finalized yet, so keep this trivially swappable.
- **Backend orchestrates the LLM, not the frontend.** Prompts and API keys stay server-side.
- **Session state lives in Postgres, not in-memory** — interviews must be resumable after a refresh/drop.
- **Server-side hard stop on session duration/turns**, independent of model behavior.
- Feature IDs (`FL-01` … `FL-09` in `docs/Feature-List-Phase1.md`) are referenced in router docstrings — keep that traceability when adding endpoints.

## Documentation policy

**Do not write new documentation files.** Keep `docs/Architecture-Decisions.md` (the ADR) updated as decisions are made or changed — that's the only doc that must stay current. Fuller documentation is deliberately deferred until later in the build.

## Branching

Git-flow: `main` (deployable releases only), `develop` (integration branch), `feature/*` off `develop`, `release/*` and `hotfix/*` off `main`/`develop` per standard git-flow. Don't commit directly to `main`.

## Memory

An auto-memory system tracks pending/completed work and decisions across sessions (see `~/.claude/projects/.../memory/MEMORY.md` if available in your environment). Check it at the start of a session for current status before assuming the state of the project.
