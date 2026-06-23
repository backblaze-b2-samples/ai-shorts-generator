"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, getClipDownloadUrl, getClipPreviewUrl } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import type { ClipItem } from "@ai-shorts-generator/shared";

interface ClipCardProps {
  clip: ClipItem;
}

export function ClipCard({ clip }: ClipCardProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Presigned preview URLs are short-lived, so we fetch on demand (when the
  // user clicks the poster) rather than for every card on page load.
  const loadPreview = async () => {
    if (previewUrl || loadingPreview) return;
    setLoadingPreview(true);
    try {
      const { url } = await getClipPreviewUrl(clip.key);
      setPreviewUrl(url);
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Failed to load preview";
      toast.error(detail);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const { url } = await getClipDownloadUrl(clip.key);
      window.open(url, "_blank");
    } catch (err) {
      const detail = err instanceof ApiError ? err.message : "Failed to get download URL";
      toast.error(detail);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Card className="overflow-hidden card-hover">
      <div className="relative aspect-[9/16] bg-muted/40">
        {previewUrl ? (
          // Inline 9:16 player using the presigned (streamable) preview URL.
          <video
            src={previewUrl}
            controls
            autoPlay
            className="h-full w-full object-contain bg-black"
          />
        ) : (
          <button
            type="button"
            onClick={loadPreview}
            disabled={loadingPreview}
            className="flex h-full w-full flex-col items-center justify-center gap-2 text-muted-foreground transition-colors hover:bg-accent/40"
          >
            {loadingPreview ? (
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            ) : (
              <>
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-foreground/80 text-background">
                  <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden>
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </div>
                <span className="text-xs font-medium">Play preview</span>
              </>
            )}
          </button>
        )}
      </div>
      <CardContent className="space-y-2 p-3">
        <p className="truncate text-sm font-medium" title={clip.filename}>
          {clip.filename}
        </p>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="font-mono tabular-nums">{clip.size_human}</span>
          <span>{formatDate(clip.uploaded_at)}</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="h-7 w-full text-xs"
          onClick={handleDownload}
          disabled={downloading}
        >
          {downloading ? (
            <Skeleton className="h-3 w-16" />
          ) : (
            <>
              <Download className="mr-1.5 h-3.5 w-3.5" />
              Download
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
