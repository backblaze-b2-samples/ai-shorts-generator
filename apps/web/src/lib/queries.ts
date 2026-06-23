"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  deleteFile,
  getClips,
  getClipsStats,
  getFiles,
  getFileStats,
  getJob,
  getPreviewUrl,
  getUploadActivity,
  startJob,
} from "@/lib/api-client";
import type {
  ClipItem,
  ClipsStats,
  FileMetadata,
  JobCreateResponse,
  JobRecord,
} from "@ai-shorts-generator/shared";

// Single source of truth for query keys. Keep these tightly scoped so that
// invalidating "files" doesn't blow away unrelated caches, and so an IDE
// "find usages" of `qk.files` reveals every consumer.
export const qk = {
  all: ["b2"] as const,
  files: (prefix?: string, limit?: number) =>
    [...qk.all, "files", prefix ?? "", limit ?? 100] as const,
  stats: () => [...qk.all, "stats"] as const,
  uploadActivity: (days: number) =>
    [...qk.all, "stats", "activity", days] as const,
  preview: (key: string) => [...qk.all, "preview", key] as const,
  job: (id: string) => [...qk.all, "job", id] as const,
  clips: () => [...qk.all, "clips"] as const,
  clipsStats: () => [...qk.all, "clips", "stats"] as const,
};

export function useFiles(prefix = "", limit = 100) {
  return useQuery<FileMetadata[], ApiError>({
    queryKey: qk.files(prefix, limit),
    queryFn: () => getFiles(prefix, limit),
  });
}

export function useFileStats() {
  return useQuery({
    queryKey: qk.stats(),
    queryFn: getFileStats,
  });
}

export function useUploadActivity(days = 7) {
  return useQuery({
    queryKey: qk.uploadActivity(days),
    queryFn: () => getUploadActivity(days),
  });
}

// Presigned preview URL — only fetched when `enabled` is true (e.g., when
// the dialog opens for a specific file). Kept short-lived (60s) because
// the URL itself has a presigned expiry and is cheap to regenerate.
export function usePreviewUrl(key: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: qk.preview(key ?? ""),
    queryFn: () => getPreviewUrl(key as string),
    enabled: enabled && !!key,
    staleTime: 60_000,
  });
}

export function useDeleteFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (fileKey: string) => deleteFile(fileKey),
    // After delete, blow away every cached file list + stats. Cheap and
    // correct — the dashboard re-fetches lazily as components remount.
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.all });
    },
  });
}

// --- AI Shorts pipeline: clips library, stats, and jobs ---

/** Rendered clips under this app's clips/ prefix (most recent first). */
export function useClips() {
  return useQuery<ClipItem[], ApiError>({
    queryKey: qk.clips(),
    queryFn: getClips,
  });
}

/** Shorts dashboard metrics (videos processed, clips generated, storage). */
export function useClipsStats() {
  return useQuery<ClipsStats, ApiError>({
    queryKey: qk.clipsStats(),
    queryFn: getClipsStats,
  });
}

// A job is finished once it reaches one of these states — stop polling then.
const TERMINAL_JOB_STATUSES: ReadonlySet<JobRecord["status"]> = new Set([
  "complete",
  "failed",
]);

/**
 * Poll a single job's status. Only fetches while `jobId` is set; refetches
 * every 2s until the job reaches a terminal state, then stops. Pass
 * `enabled: false` to pause (e.g. before a job has been started).
 */
export function useJob(jobId: string | undefined, options?: { enabled?: boolean }) {
  const enabled = (options?.enabled ?? true) && !!jobId;
  return useQuery<JobRecord, ApiError>({
    queryKey: qk.job(jobId ?? ""),
    queryFn: () => getJob(jobId as string),
    enabled,
    // Poll while running; once terminal, `false` stops the interval.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && TERMINAL_JOB_STATUSES.has(status)) return false;
      return 2_000;
    },
  });
}

/**
 * Start a shorts job (uploads the source video + enqueues processing).
 * On success, seed the job cache and invalidate the clips library/stats so
 * they refresh as the pipeline produces output.
 */
export function useStartJob() {
  const qc = useQueryClient();
  return useMutation<
    JobCreateResponse,
    ApiError,
    { file: File; clipCount: number; aspect: string; onProgress?: (p: number) => void }
  >({
    mutationFn: ({ file, clipCount, aspect, onProgress }) =>
      startJob(file, { clipCount, aspect }, onProgress),
    onSuccess: (job) => {
      qc.invalidateQueries({ queryKey: qk.job(job.id) });
      qc.invalidateQueries({ queryKey: qk.clips() });
      qc.invalidateQueries({ queryKey: qk.clipsStats() });
    },
  });
}
