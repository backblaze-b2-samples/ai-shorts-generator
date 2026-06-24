"use client";

import { ChevronDown, ChevronRight, Folder, FolderOpen } from "lucide-react";

import { ClipCard } from "./clip-card";
import { formatDate } from "@/lib/utils";
import type { ClipItem } from "@ai-shorts-generator/shared";

interface ClipFolderProps {
  jobId: string;
  clips: ClipItem[];
  isOpen: boolean;
  onToggle: (jobId: string) => void;
}

/**
 * One source video's shorts, as a collapsible folder. The label prefers the
 * source video's filename/date (carried on each ClipItem from its job record);
 * clips rendered before that enrichment existed fall back to the job id and the
 * clip's own upload time.
 */
export function ClipFolder({ jobId, clips, isOpen, onToggle }: ClipFolderProps) {
  const first = clips[0];
  const label = first?.source_filename ?? `Job ${jobId}`;
  const when = first?.job_created_at ?? first?.uploaded_at;

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => onToggle(jobId)}
        className="flex w-full items-center gap-2 rounded-t-lg px-4 py-3 text-sm transition-colors hover:bg-accent/60"
      >
        {isOpen ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        {isOpen ? (
          <FolderOpen className="h-4 w-4 shrink-0 text-[var(--attention)]" />
        ) : (
          <Folder className="h-4 w-4 shrink-0 text-[var(--attention)]" />
        )}
        <span className="truncate font-medium" title={label}>
          {label}
        </span>
        {when && (
          <span className="hidden text-xs text-muted-foreground sm:inline">
            {formatDate(when)}
          </span>
        )}
        <span className="ml-auto shrink-0 text-xs text-muted-foreground">
          {clips.length} {clips.length === 1 ? "clip" : "clips"}
        </span>
      </button>
      {isOpen && (
        <div className="grid gap-4 border-t border-border p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {clips.map((clip) => (
            <ClipCard key={clip.key} clip={clip} />
          ))}
        </div>
      )}
    </div>
  );
}
