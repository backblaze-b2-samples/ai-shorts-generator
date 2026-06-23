"use client";

import Link from "next/link";
import { Clapperboard, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ClipCard } from "./clip-card";
import { useClips } from "@/lib/queries";

export function ClipLibrary() {
  const { data: clips = [], isLoading, isFetching, error, refetch } = useClips();

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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {clips.map((clip) => (
              <ClipCard key={clip.key} clip={clip} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
