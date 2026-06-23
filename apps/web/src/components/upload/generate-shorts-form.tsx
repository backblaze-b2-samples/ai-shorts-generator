"use client";

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Film, Sparkles, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { JobProgress } from "./job-progress";
import { useStartJob } from "@/lib/queries";
import { humanizeBytes } from "@/lib/utils";

// Backend caps source videos at 1 GiB and accepts mp4/mov/webm/mkv.
const MAX_SIZE = 1024 * 1024 * 1024;
const ACCEPT = {
  "video/mp4": [".mp4"],
  "video/quicktime": [".mov"],
  "video/webm": [".webm"],
  "video/x-matroska": [".mkv"],
};

export function GenerateShortsForm() {
  const [file, setFile] = useState<File | null>(null);
  const [clipCount, setClipCount] = useState("3");
  const [aspect, setAspect] = useState("9:16");
  const [progress, setProgress] = useState(0);
  const [jobId, setJobId] = useState<string | null>(null);

  const startJob = useStartJob();

  const onDrop = useCallback((accepted: File[]) => {
    if (accepted.length > 0) {
      setFile(accepted[0]);
      setJobId(null);
    }
  }, []);

  const onDropRejected = useCallback((rejections: FileRejection[]) => {
    for (const r of rejections) {
      const reason = r.errors.some((e) => e.code === "file-too-large")
        ? `exceeds 1 GB limit (${humanizeBytes(r.file.size)})`
        : "must be a video (mp4, mov, webm, mkv)";
      toast.error(`${r.file.name}: ${reason}`);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: ACCEPT,
    maxSize: MAX_SIZE,
    multiple: false,
    disabled: startJob.isPending,
  });

  const handleGenerate = () => {
    if (!file) return;
    setProgress(0);
    startJob.mutate(
      {
        file,
        clipCount: Number(clipCount),
        aspect,
        onProgress: setProgress,
      },
      {
        onSuccess: (job) => {
          setJobId(job.id);
          toast.success("Video uploaded — generating shorts");
        },
        onError: (err) => toast.error(err.message),
      },
    );
  };

  const isUploading = startJob.isPending;

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Generate Shorts</CardTitle>
      </CardHeader>
      <CardContent className="p-5 space-y-4">
        {file ? (
          <div className="flex items-center gap-3 rounded-md border border-border bg-card p-3">
            <Film className="h-6 w-6 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{file.name}</p>
              <p className="font-mono text-xs text-muted-foreground">
                {humanizeBytes(file.size)}
              </p>
            </div>
            {!isUploading && !jobId && (
              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setFile(null)}>
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        ) : (
          <div
            {...getRootProps()}
            className={`flex flex-col items-center justify-center rounded-md border-2 border-dashed p-10 text-center transition-colors cursor-pointer ${
              isDragActive
                ? "border-primary bg-[var(--accent-subtle)] dropzone-active"
                : "border-border hover:border-primary/60 hover:bg-muted/60"
            }`}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-3">
              <div className="flex items-center justify-center w-12 h-12 rounded-md bg-muted border border-border">
                <Film className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-base font-semibold">
                  Drop a long video here, or click to browse
                </p>
                <p className="text-xs text-muted-foreground mt-1 font-mono">
                  mp4, mov, webm, mkv · up to 1 GB
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="clip-count">Number of clips</Label>
            <Select value={clipCount} onValueChange={setClipCount} disabled={isUploading}>
              <SelectTrigger id="clip-count">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {["1", "2", "3", "5", "8"].map((n) => (
                  <SelectItem key={n} value={n}>
                    {n} {n === "1" ? "clip" : "clips"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="aspect">Aspect ratio</Label>
            <Select value={aspect} onValueChange={setAspect} disabled={isUploading}>
              <SelectTrigger id="aspect">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="9:16">9:16 (vertical)</SelectItem>
                <SelectItem value="4:5">4:5 (portrait)</SelectItem>
                <SelectItem value="1:1">1:1 (square)</SelectItem>
                <SelectItem value="16:9">16:9 (landscape)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {isUploading && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Uploading source video…</p>
            <Progress value={progress} className="h-1 progress-gradient" />
          </div>
        )}

        <Button
          className="w-full"
          disabled={!file || isUploading}
          onClick={handleGenerate}
        >
          <Sparkles className="h-4 w-4" />
          {isUploading ? "Uploading…" : "Generate shorts"}
        </Button>

        {jobId && <JobProgress jobId={jobId} />}
      </CardContent>
    </Card>
  );
}
