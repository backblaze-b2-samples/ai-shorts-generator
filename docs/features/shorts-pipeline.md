<!-- last_verified: 2026-06-23 -->
# Feature: Shorts Pipeline

## Purpose
Turn one long source video into several share-ready vertical clips with burned-in
captions: upload → transcribe → score the best moments (LLM) → render → store on B2.

## Used By
- UI: `/upload` page (Generate Shorts form + live job progress), `/clips` library, dashboard stats
- API: `POST /jobs`, `GET /jobs/{job_id}`, `GET /clips`, `GET /clips/stats`, `GET /clips/{key}/preview`, `GET /clips/{key}/download`
- Job: `run_job()` background task (FastAPI `BackgroundTasks`)

## Core Functions
- `apps/web/src/components/upload/generate-shorts-form.tsx` — pick a video + clip count/aspect, start a job
- `apps/web/src/components/upload/job-progress.tsx` — polls job status, renders the stage/progress, links to clips on completion
- `apps/web/src/components/clips/clip-library.tsx` + `clip-card.tsx` — grid of rendered clips with inline `<video>` preview + download
- `apps/web/src/lib/api-client.ts` — `startJob()`, `getJob()`, `getClips()`, `getClipsStats()`, `getClipPreviewUrl()`, `getClipDownloadUrl()`
- `apps/web/src/lib/queries.ts` — `useStartJob()`, `useJob()` (polling), `useClips()`, `useClipsStats()`
- `services/api/app/runtime/jobs.py` — `POST /jobs` handler (uploads source, enqueues `run_job`), `GET /jobs/{id}`
- `services/api/app/runtime/clips.py` — clips library + stats routes
- `services/api/app/service/jobs.py` — `create_job()`, `run_job()` pipeline orchestration, B2-as-datastore status persistence
- `services/api/app/service/clips.py` — `list_clips()`, `get_shorts_stats()`, presigned URL helpers (clips/ prefix only)
- `services/api/app/service/render.py` — `extract_audio()`, `detect`/render helpers, `build_srt()`, `render_clip()` (ffmpeg)
- `services/api/app/repo/` — `transcribe_audio()`, `detect_moments()` (Genblaze/OpenAI), B2 `upload_file`/`upload_path`/`get_json`/`put_json`/`download_file`

## Canonical Files
- Job handler pattern: `services/api/app/runtime/jobs.py`
- Pipeline orchestration pattern: `services/api/app/service/jobs.py`
- Frontend job-driven flow: `apps/web/src/components/upload/generate-shorts-form.tsx`

## Inputs
- file: `File` — the source video (multipart form data). Allowed types: `video/mp4`, `video/quicktime`, `video/webm`, `video/x-matroska`. Max 1 GiB.
- clip_count: int (form field, default `0` → falls back to `settings.clips_per_video`, default 3)
- aspect: string (form field, default `""` → falls back to `settings.clip_aspect`, default `9:16`)

## Outputs
- `POST /jobs` → `JobCreateResponse` `{ id, status }`
- `GET /jobs/{id}` → `JobRecord` `{ id, status, source_key, source_filename, clip_count, aspect, created_at, updated_at, progress, message, moments[], clips[], error }`
  - `status`: `queued | transcribing | detecting | rendering | complete | failed`
  - `clips[]`: `ClipResult` `{ key, title, duration_seconds, size_bytes }`
- `GET /clips` → `ClipItem[]` `{ key, filename, job_id, size_bytes, size_human, uploaded_at }` (most recent first)
- `GET /clips/stats` → `ClipsStats` `{ videos_processed, clips_generated, total_clip_seconds, storage_bytes, storage_human }`
- `GET /clips/{key}/preview` → `{ url }` (inline/streamable presigned URL for `<video>`)
- `GET /clips/{key}/download` → `{ url }` (attachment presigned URL)
- Side effects (all on B2, the sole datastore):
  - source at `sources/<uuid>/<filename>`
  - job record at `jobs/<id>.json` (rewritten after each stage transition)
  - transcript at `transcripts/<id>.json`, moments at `moments/<id>.json`
  - rendered clips at `clips/<id>/clip_N.mp4`, caption tracks at `captions/<id>/clip_N.srt`

## Flow
- User drops a video and picks clip count + aspect on `/upload`, then clicks Generate shorts
- Client `startJob()` POSTs multipart `file` + `clip_count` + `aspect` to `/jobs` (XHR, upload progress)
- API validates content type (415 if unsupported) and size (413 if > 1 GiB), rejects empty files (400)
- API sanitizes the filename, uploads the source to `sources/<uuid>/`, creates the job record (`queued`), enqueues `run_job` as a background task, returns `{ id, status }`
- `useJob(id)` polls `GET /jobs/{id}` every 2s; UI shows the stage label + `progress`
- `run_job` pipeline: download source → extract audio → transcribe (Whisper, `transcribing`, 10–25%) → detect best moments via LLM (`detecting`, 50%) → render each clip with burned-in captions and upload to `clips/<id>/` (`rendering`, 65–95%) → mark `complete` (100%)
- On completion, `useJob` stops polling (terminal status), the progress card links to `/clips`
- `/clips` lists rendered clips via `GET /clips`; each card lazily fetches a streamable preview URL for inline playback and a separate attachment URL for download
- The dashboard `useClipsStats()` shows videos processed, clips generated, total clip length, and storage used

## Edge Cases
- Unsupported source type → API returns 415
- Source video > 1 GiB → API returns 413 (client also rejects with a toast before upload)
- Empty file → API returns 400
- Job id not found → `GET /jobs/{id}` returns 404; UI shows an error card
- Pipeline step throws (transcription/detection/render failure) → job persisted as `failed` with `error` set; UI shows the error message, polling stops
- Clip key outside the `clips/` prefix or containing path-traversal → preview/download return 400 (`ClipKeyError`)
- No clips yet → `/clips` shows an EmptyState with a "Generate shorts" call to action

## UX States
- Empty: `/clips` EmptyState; dashboard stats render zeros
- Loading: upload progress bar during source upload; per-card skeletons in the clips grid; polling spinner on the job card
- Running: stage label (Transcribing / Scoring moments / Rendering) + percentage progress bar
- Error: job-failed card with the backend error message; toast on start/preview/download failures
- Complete: green check, "View N clips" link to `/clips`

## Verification
- Test files: `services/api/tests/` (backend job/clip routes + `tests/test_structure.py` for boundaries)
- Required cases: start job happy path, unsupported type rejected, oversized/empty rejected, job-not-found 404, clip key validation, clips list + stats
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm build && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: lint clean, Next build/type-check succeeds, all pytest tests green, no ruff violations

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [File Upload](file-upload.md)
- [App Workflows](../app-workflows.md)
