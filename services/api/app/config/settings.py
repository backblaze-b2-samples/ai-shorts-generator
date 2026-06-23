from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Backblaze B2 (S3-compatible) ---
    # Standardized B2_* env names. The S3 endpoint is derived from B2_REGION
    # (https://s3.{region}.backblazeb2.com); B2_ENDPOINT may override it if
    # set, but is not required.
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_region: str = ""
    b2_public_url_base: str = ""
    # Optional explicit endpoint override. Empty by default — leave unset and
    # the endpoint is computed from b2_region.
    b2_endpoint: str = ""

    # --- AI moment detection / captioning (OpenAI via the Genblaze SDK) ---
    # OPENAI_API_KEY is the app's ONE external AI key. Anthropic/Claude is not
    # available through Genblaze, so the next supported provider (OpenAI) drives
    # the core moment-scoring + captioning step.
    openai_api_key: str = ""
    shorts_model: str = "gpt-4o-mini"

    # --- Transcription ---
    # Local & keyless by default (faster-whisper). Set TRANSCRIPTION_BACKEND
    # to "openai" to use the remote Whisper API — it reuses OPENAI_API_KEY.
    transcription_backend: str = "local"
    whisper_model: str = "base.en"

    # --- Clip rendering defaults ---
    clips_per_video: int = 3
    clip_aspect: str = "9:16"

    api_port: int = 8000
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Small durable counters (downloads, etc). Point at a persistent
    # volume in production if you care about surviving restarts.
    download_count_file: str = "data/download_count.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def endpoint_url(self) -> str:
        """Resolve the S3 endpoint. Prefer an explicit B2_ENDPOINT override;
        otherwise derive it from B2_REGION. No region is ever hardcoded here —
        it comes entirely from configuration."""
        if self.b2_endpoint:
            return self.b2_endpoint
        if self.b2_region:
            return f"https://s3.{self.b2_region}.backblazeb2.com"
        return ""


settings = Settings()
