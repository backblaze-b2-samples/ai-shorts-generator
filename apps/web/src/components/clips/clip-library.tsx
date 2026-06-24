"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Clapperboard, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ClipFolder } from "./clip-folder";
import { useClips } from "@/lib/queries";
import type { ClipItem } from "@ai-shorts-generator/shared";

interface ClipGroup {
  jobId: string;
  clips: ClipItem[];
}

// Group clips into one folder per source video (job), newest folder first.
// Clips arrive already sorted newest-first, so the first clip in each group is
// its most recent — we sort groups by that and keep the in-group order as-is.
function groupClipsByJob(clips: ClipItem[]): ClipGroup[] {
  const byJob = new Map<string, ClipItem[]>();
  for (const clip of clips) {
    const list = byJob.get(clip.job_id);
    if (list) list.push(clip);
    else byJob.set(clip.job_id, [clip]);
  }
  const sortKey = (c: ClipItem) => c.job_created_at ?? c.uploaded_at;
  return Array.from(byJob.entries())
    .map(([jobId, groupClips]) => ({ jobId, clips: groupClips }))
    .sort((a, b) => sortKey(b.clips[0]).localeCompare(sortKey(a.clips[0])));
}

export function ClipLibrary() {
  const { data: clips = [], isLoading, isFetching, error, refetch } = useClips();

  const groups = useMemo(() => groupClipsByJob(clips), [clips]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Expand every folder the first time data arrives. Guarded on `prev.size > 0`
  // so it runs once — after that the user's expand/collapse choices stick across
  // refetches (mirrors the File Explorer's behavior).
  useEffect(() => {
    if (groups.length === 0) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setExpanded((prev) => {
      if (prev.size > 0) return prev;
      return new Set(groups.map((g) => g.jobId));
    });
  }, [groups]);

  const toggleFolder = useCallback((jobId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  }, []);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between border-b border-border py-4 px-5 space-y-0">
        <CardTitle className="card-title">Rendered Clips</CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          className="h-7 text-xs"
          disabled={isFetching}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="aspect-[9/16] w-full rounded-lg" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : clips.length === 0 ? (
          <EmptyState
            icon={Clapperboard}
            title="No clips yet"
            description="Upload a video and generate shorts — rendered clips show up here."
            action={
              <Button asChild size="sm">
                <Link href="/upload">Generate shorts</Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {groups.map((group) => (
              <ClipFolder
                key={group.jobId}
                jobId={group.jobId}
                clips={group.clips}
                isOpen={expanded.has(group.jobId)}
                onToggle={toggleFolder}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
