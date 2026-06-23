"use client";

import Link from "next/link";
import { CheckCircle2, Clapperboard, Loader2, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useJob } from "@/lib/queries";
import type { JobStatus } from "@ai-shorts-generator/shared";

// Human-readable label per pipeline stage. Matches the backend JobStatus
// transitions emitted by services/api/app/service/jobs.py.
const STAGE_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  transcribing: "Transcribing audio",
  detecting: "Scoring the best moments",
  rendering: "Rendering vertical clips",
  complete: "Done",
  failed: "Failed",
};

interface JobProgressProps {
  jobId: string;
}

export function JobProgress({ jobId }: JobProgressProps) {
  const { data: job, error } = useJob(jobId);

  if (error) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
        <p className="flex items-center gap-2 font-medium text-destructive">
          <XCircle className="h-4 w-4" />
          Couldn&apos;t read job status
        </p>
        <p className="mt-1 text-muted-foreground">{error.message}</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Starting job...
      </div>
    );
  }

  const isComplete = job.status === "complete";
  const isFailed = job.status === "failed";

  return (
    <div className="space-y-3 rounded-md border border-border bg-card p-4 animate-fade-in-up">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          {isComplete ? (
            <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />
          ) : isFailed ? (
            <XCircle className="h-4 w-4 text-destructive" />
          ) : (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          )}
          {STAGE_LABELS[job.status]}
        </div>
        <span className="font-mono text-xs text-muted-foreground tabular-nums">
          {job.progress}%
        </span>
      </div>

      <Progress value={job.progress} className="h-1 progress-gradient" />

      <p className="text-xs text-muted-foreground">
        {isFailed ? (job.error ?? job.message) : job.message}
      </p>

      {isComplete && (
        <Button asChild size="sm" className="h-8">
          <Link href="/clips">
            <Clapperboard className="h-3.5 w-3.5" />
            View {job.clips.length} {job.clips.length === 1 ? "clip" : "clips"}
          </Link>
        </Button>
      )}
    </div>
  );
}
