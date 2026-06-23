import { GenerateShortsForm } from "@/components/upload/generate-shorts-form";
import { UploadForm } from "@/components/upload/upload-form";

export default function UploadPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Upload</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Drop a long video to generate AI shorts, or upload any file to your
          bucket.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <GenerateShortsForm />
      </div>
      <div className="animate-fade-in-up stagger-3 space-y-2">
        <p className="text-sm font-semibold text-muted-foreground">
          Or upload a file directly
        </p>
        <UploadForm />
      </div>
    </div>
  );
}
