"""Prepare the sequential baseline and unbiased per-class reservoir samples."""
import gzip
import json
import random
from collections import Counter
from common import ROOT, CLASSES, file_hash, label, write_json, write_jsonl

SEED = 6418
PER_CLASS = 50
SOURCE = ROOT / "data/Gift_Cards.jsonl.gz"


def prepare(source=SOURCE, seed=SEED, per_class=PER_CLASS):
    rng = {c: random.Random(f"{seed}:{c}") for c in CLASSES}
    pools = {c: [] for c in CLASSES}
    counts, stars = Counter(), Counter()
    first = []
    with gzip.open(source, "rt", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            row = json.loads(line)
            cls = label(row["rating"])
            if not isinstance(row["title"], str) or not isinstance(row["text"], str):
                raise ValueError(f"Missing review text at line {line_no}")
            # Stable source IDs; omit reviewer IDs and images from distributable samples.
            record = {k: row[k] for k in ("title", "text", "rating", "asin", "parent_asin", "verified_purchase", "helpful_vote", "timestamp")}
            record.update(review_id=f"gift_cards:{line_no}", source_line=line_no)
            if len(first) < 100:
                first.append(record)
            counts[cls] += 1
            stars[str(int(row["rating"]))] += 1
            if len(pools[cls]) < per_class:
                pools[cls].append(record)
            else:
                slot = rng[cls].randrange(counts[cls])
                if slot < per_class:
                    pools[cls][slot] = record
    if len(first) != 100 or any(len(pools[c]) != per_class for c in CLASSES):
        raise ValueError("Insufficient data for requested samples")
    balanced = sorted([r for c in CLASSES for r in pools[c]], key=lambda r: r["source_line"])
    return first, balanced, {
        "source_url": "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Gift_Cards.jsonl.gz",
        "dataset_page": "https://amazon-reviews-2023.github.io/", "source_sha256": file_hash(source),
        "population_size": sum(counts.values()), "population_classes": dict(counts),
        "population_stars": dict(sorted(stars.items())), "seed": seed, "per_class": per_class,
        "sampling": "Independent seeded uniform reservoir sampling within each rating class across the entire file; no replacement. Saved order is source-line order.",
        "baseline_ids": [r["review_id"] for r in first], "balanced_ids": [r["review_id"] for r in balanced],
        "sample_overlap": sorted(set(r["review_id"] for r in first) & set(r["review_id"] for r in balanced)),
    }


if __name__ == "__main__":
    first, balanced, manifest = prepare()
    out = ROOT / "data/prepared"
    write_jsonl(out / "baseline_100.jsonl", first)
    write_jsonl(out / "balanced_150.jsonl", balanced)
    write_jsonl(out / "smoke.jsonl", [
        {"review_id": "synthetic:positive", "title": "Perfect gift", "text": "Easy to send and worked immediately. I loved it!", "expected": "POSITIVE"},
        {"review_id": "synthetic:negative", "title": "Unusable", "text": "The code did not work and support refused to help. Terrible experience.", "expected": "NEGATIVE"},
        {"review_id": "synthetic:conflict", "title": "Great", "text": "Actually the card never arrived and I could not get a refund. I regret buying it.", "expected": "NEGATIVE"},
        {"review_id": "synthetic:short", "title": "Love it", "text": "Excellent!", "expected": "POSITIVE"},
    ])
    write_json(out / "sampling_manifest.json", manifest)
    print(f"Prepared {len(first)} baseline and {len(balanced)} balanced reviews from {manifest['population_size']} rows")
