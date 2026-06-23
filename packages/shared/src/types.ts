export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- AI Shorts pipeline ---

export type JobStatus =
  | "queued"
  | "transcribing"
  | "detecting"
  | "rendering"
  | "complete"
  | "failed";

export interface Moment {
  start: number;
  end: number;
  title: string;
  hook: string;
  caption_lines: string[];
}

export interface ClipResult {
  key: string;
  title: string;
  duration_seconds: number;
  size_bytes: number;
}

export interface JobRecord {
  id: string;
  status: JobStatus;
  source_key: string;
  source_filename: string;
  clip_count: number;
  aspect: string;
  created_at: string;
  updated_at: string;
  progress: number;
  message: string;
  moments: Moment[];
  clips: ClipResult[];
  error: string | null;
}

export interface JobCreateResponse {
  id: string;
  status: JobStatus;
}

export interface ClipItem {
  key: string;
  filename: string;
  job_id: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
}

export interface ClipsStats {
  videos_processed: number;
  clips_generated: number;
  total_clip_seconds: number;
  storage_bytes: number;
  storage_human: string;
}
