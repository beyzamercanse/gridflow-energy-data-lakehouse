"""S3/MinIO Bronze and Silver persistence using immutable, content-addressed keys."""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.config import Config
from botocore.exceptions import ClientError

from gridflow.store import SavedBatch


@dataclass(frozen=True)
class LakeSettings:
    endpoint_url: str
    access_key: str
    secret_key: str
    bucket: str
    region: str = "us-east-1"

    @classmethod
    def from_env(cls) -> LakeSettings:
        required = ("S3_ENDPOINT_URL", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY", "S3_BUCKET")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError("Missing S3 configuration: " + ", ".join(missing))
        return cls(
            endpoint_url=os.environ["S3_ENDPOINT_URL"],
            access_key=os.environ["S3_ACCESS_KEY_ID"],
            secret_key=os.environ["S3_SECRET_ACCESS_KEY"],
            bucket=os.environ["S3_BUCKET"],
            region=os.getenv("S3_REGION", "us-east-1"),
        )


@dataclass(frozen=True)
class ObjectResult:
    key: str
    sha256: str
    created: bool
    size_bytes: int


class ObjectLake:
    """Small S3/MinIO adapter; no credentials are stored in keys or metadata."""

    def __init__(self, settings: LakeSettings, client: Any | None = None) -> None:
        self.settings = settings
        self.client = client or boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            region_name=settings.region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.settings.bucket)
        except ClientError as exc:
            status = str(exc.response.get("Error", {}).get("Code"))
            if status not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            options: dict[str, Any] = {"Bucket": self.settings.bucket}
            if self.settings.region != "us-east-1":
                options["CreateBucketConfiguration"] = {
                    "LocationConstraint": self.settings.region
                }
            self.client.create_bucket(**options)

    def put_immutable(self, key: str, body: bytes, *, content_type: str) -> ObjectResult:
        """Atomically create an object if absent; reject a mismatched-key collision."""
        digest = hashlib.sha256(body).hexdigest()
        try:
            self.client.put_object(
                Bucket=self.settings.bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={"sha256": digest},
                IfNoneMatch="*",
            )
            return ObjectResult(key, digest, True, len(body))
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code"))
            if code not in {"PreconditionFailed", "412"}:
                raise
        head = self.client.head_object(Bucket=self.settings.bucket, Key=key)
        if head.get("Metadata", {}).get("sha256") != digest:
            raise ValueError(f"S3 content-addressed key collision: {key}")
        return ObjectResult(key, digest, False, len(body))

    def read_bytes(self, key: str) -> bytes:
        answer = self.client.get_object(Bucket=self.settings.bucket, Key=key)
        return answer["Body"].read()

    def upload_bronze(
        self, batch: SavedBatch, *, source: str, day: date
    ) -> tuple[ObjectResult, ObjectResult]:
        if source not in {"energy_price", "weather_hourly"}:
            raise ValueError("Unsupported source")
        prefix = f"bronze/source={source}/date={day.isoformat()}/{batch.sha256}"
        raw = batch.content_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != batch.sha256:
            raise ValueError("Local Bronze payload checksum mismatch")
        content = self.put_immutable(prefix + ".json", raw, content_type="application/json")
        metadata = self.put_immutable(
            prefix + ".metadata.json",
            batch.metadata_path.read_bytes(),
            content_type="application/json",
        )
        return content, metadata

    def upload_silver(
        self,
        table: pa.Table,
        *,
        source: str,
        partition: str,
        day: date,
        source_sha256: str,
    ) -> ObjectResult:
        _check_partition(source, partition, source_sha256)
        key = (
            f"silver/source={source}/partition={partition}/date={day.isoformat()}/"
            f"source_sha256={source_sha256}/part-000.parquet"
        )
        stream = io.BytesIO()
        pq.write_table(table, stream, compression="zstd", version="2.6")
        return self.put_immutable(
            key, stream.getvalue(), content_type="application/vnd.apache.parquet"
        )


def _check_partition(source: str, partition: str, digest: str) -> None:
    if source not in {"energy_price", "weather_hourly"}:
        raise ValueError("Unsupported source")
    if not partition or not all(c.isascii() and (c.isalnum() or c in "_-") for c in partition):
        raise ValueError("Partition label must be a safe slug")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid source SHA-256")


def write_local_silver(
    table: pa.Table,
    directory: Path,
    *,
    source: str,
    partition: str,
    day: date,
    source_sha256: str,
) -> Path:
    _check_partition(source, partition, source_sha256)
    path = (
        directory / source / f"partition={partition}" / f"date={day.isoformat()}"
        / f"source_sha256={source_sha256}" / "part-000.parquet"
    )
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".parquet.tmp")
        pq.write_table(table, temporary, compression="zstd", version="2.6")
        temporary.replace(path)
    return path

