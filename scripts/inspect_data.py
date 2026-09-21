#!/usr/bin/env python3
"""Stream-inspect the compressed Amazon Reviews 2023 Gift Cards file."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXPECTED_FIELDS = {
    "rating",
    "title",
    "text",
    "images",
    "asin",
    "parent_asin",
    "user_id",
    "timestamp",
    "helpful_vote",
    "verified_purchase",
}


def iso_utc(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()


def sentiment_class(rating: float) -> str:
    if rating >= 4:
        return "POSITIVE"
    if rating == 3:
        return "NEUTRAL"
    return "NEGATIVE"


def inspect(path: Path, sample_size: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row_count = 0
    malformed_rows = 0
    field_counts: Counter[str] = Counter()
    field_types: dict[str, Counter[str]] = {}
    rating_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    missing_or_null: Counter[str] = Counter()
    verified_counts: Counter[str] = Counter()
    users: set[str] = set()
    asins: set[str] = set()
    parent_asins: set[str] = set()
    samples: list[dict[str, Any]] = []
    min_timestamp: int | None = None
    max_timestamp: int | None = None
    helpful_total = 0
    reviews_with_images = 0

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed_rows += 1
                continue

            row_count += 1
            if len(samples) < sample_size:
                samples.append(row)

            field_counts.update(row.keys())
            for field in EXPECTED_FIELDS:
                value = row.get(field)
                if value is None:
                    missing_or_null[field] += 1
                else:
                    field_types.setdefault(field, Counter()).update([type(value).__name__])

            rating = row.get("rating")
            if isinstance(rating, (int, float)):
                rating_counts[str(int(rating))] += 1
                class_counts[sentiment_class(float(rating))] += 1

            verified_counts[str(row.get("verified_purchase"))] += 1
            helpful = row.get("helpful_vote")
            if isinstance(helpful, int):
                helpful_total += helpful
            if row.get("images"):
                reviews_with_images += 1

            if row.get("user_id"):
                users.add(row["user_id"])
            if row.get("asin"):
                asins.add(row["asin"])
            if row.get("parent_asin"):
                parent_asins.add(row["parent_asin"])

            timestamp = row.get("timestamp")
            if isinstance(timestamp, int):
                min_timestamp = timestamp if min_timestamp is None else min(min_timestamp, timestamp)
                max_timestamp = timestamp if max_timestamp is None else max(max_timestamp, timestamp)

    all_fields = sorted(field_counts)
    summary = {
        "source_file": str(path),
        "compressed_bytes": path.stat().st_size,
        "valid_rows": row_count,
        "malformed_rows": malformed_rows,
        "fields": all_fields,
        "expected_fields_present": sorted(EXPECTED_FIELDS.intersection(all_fields)),
        "unexpected_fields": sorted(set(all_fields) - EXPECTED_FIELDS),
        "field_presence_counts": dict(sorted(field_counts.items())),
        "field_types": {
            field: dict(sorted(types.items())) for field, types in sorted(field_types.items())
        },
        "missing_or_null_counts": dict(sorted(missing_or_null.items())),
        "rating_counts": dict(sorted(rating_counts.items(), key=lambda item: int(item[0]))),
        "three_class_counts": dict(sorted(class_counts.items())),
        "verified_purchase_counts": dict(sorted(verified_counts.items())),
        "unique_users": len(users),
        "unique_asins": len(asins),
        "unique_parent_asins": len(parent_asins),
        "helpful_votes_total": helpful_total,
        "reviews_with_images": reviews_with_images,
        "timestamp_range_utc": {
            "earliest": iso_utc(min_timestamp),
            "latest": iso_utc(max_timestamp),
        },
    }
    return summary, samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--summary", type=Path, default=Path("data/dataset_profile.json"))
    parser.add_argument("--samples", type=Path, default=Path("data/sample_reviews.jsonl"))
    parser.add_argument("--sample-size", type=int, default=5)
    args = parser.parse_args()

    summary, samples = inspect(args.path, args.sample_size)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.samples.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with args.samples.open("w", encoding="utf-8") as handle:
        for row in samples:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
