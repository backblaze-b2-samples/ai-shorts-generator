import Link from "next/link";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentUploadsTable } from "@/components/dashboard/recent-uploads-table";
import { UploadChart } from "@/components/dashboard/upload-chart";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Your AI shorts pipeline at a glance — videos processed, clips
            rendered, and B2 storage used.
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/upload">
            <Sparkles className="h-3.5 w-3.5" />
            Generate shorts
          </Link>
        </Button>
      </div>
      <StatsCards />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <UploadChart />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentUploadsTable />
        </div>
      </div>
    </div>
  );
}
