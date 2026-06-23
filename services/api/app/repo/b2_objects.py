"""Object-level B2 helpers for the shorts pipeline.

Split out from b2_client.py to keep both modules well under the 300-line cap.
Reuses the single cached S3 client (one client, one custom user agent) so all
B2 access carries the b2ai-ai-shorts-generator identity.
"""

import json

from botocore.exceptions import ClientError

from app.config import settings
from app.repo.b2_client import _guess_content_type, get_s3_client


def get_inline_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Presigned URL that plays inline (no attachment disposition).

    Used by the Clips page so generated mp4s can stream in a <video> tag
    instead of forcing a download. Raises RuntimeError on failure.
    """
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.b2_bucket_name,
                "Key": key,
                "ResponseContentDisposition": "inline",
                "ResponseContentType": _guess_content_type(key),
            },
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 inline presign failed for '{key}': {e}") from e


def download_file(key: str, dest_path: str) -> None:
    """Stream an object from B2 to a local path (for ffmpeg processing).

    Sustained large read — the "download the source once to process" side of
    the upload-once / read-many B2 pattern. Raises RuntimeError on failure.
    """
    client = get_s3_client()
    try:
        client.download_file(settings.b2_bucket_name, key, dest_path)
    except ClientError as e:
        raise RuntimeError(f"B2 download failed for '{key}': {e}") from e


def upload_path(local_path: str, key: str, content_type: str) -> None:
    """Upload a local file (e.g. a rendered clip) to B2 by streaming from disk.

    Avoids loading large mp4s fully into memory. Raises RuntimeError on failure.
    """
    client = get_s3_client()
    try:
        client.upload_file(
            local_path,
            settings.b2_bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except ClientError as e:
        raise RuntimeError(f"B2 upload failed for '{key}': {e}") from e


def put_json(key: str, payload: dict) -> None:
    """Persist a JSON document to B2 — job status / transcript / moments
    records. B2 is the sole datastore. Raises RuntimeError on failure."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=json.dumps(payload).encode("utf-8"),
            ContentType="application/json",
        )
    except ClientError as e:
        raise RuntimeError(f"B2 put_json failed for '{key}': {e}") from e


def get_json(key: str) -> dict | None:
    """Read a JSON document from B2. Returns None if the object is missing.
    Raises RuntimeError on other S3 failures."""
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise RuntimeError(f"B2 get_json failed for '{key}': {e}") from e
    return json.loads(response["Body"].read().decode("utf-8"))


def list_keys(prefix: str, max_keys: int = 1000) -> list[dict]:
    """List raw object summaries under a prefix (key, size, last_modified).

    Lighter than `list_files` — used by the scoped Clips library and the job
    lister. Raises RuntimeError on failure.
    """
    client = get_s3_client()
    out: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": max_keys,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            for obj in response.get("Contents", []):
                out.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                    }
                )
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for prefix '{prefix}': {e}") from e
    return out
