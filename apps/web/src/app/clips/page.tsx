import Link from "next/link";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ClipLibrary } from "@/components/clips/clip-library";

export default function ClipsPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Clips</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Every vertical short rendered from your videos, ready to preview and
            download.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/upload">
            <Sparkles className="h-3.5 w-3.5" />
            Generate shorts
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <ClipLibrary />
      </div>
    </div>
  );
}
