"""Produce an offline data contract and chart tables, but no dashboard/UI."""
import csv
import io
import json
from common import ROOT, read_jsonl, write_json


def filter_reviews(rows, *, correctness="all", sentiment=None, predicted=None, emotion_agreement="all", query=""):
    if correctness not in ("all", "correct", "mismatched") or emotion_agreement not in ("all", "agree", "disagree"):
        raise ValueError("Invalid filter value")
    query = query.casefold().strip()
    result = [r for r in rows
              if (correctness == "all" or r["correct"] == (correctness == "correct"))
              and (sentiment is None or r["true_sentiment"] == sentiment)
              and (predicted is None or r["predicted_sentiment"] == predicted)
              and (emotion_agreement == "all" or r["emotion_agree"] == (emotion_agreement == "agree"))
              and (not query or query in (r["title"] + " " + r["text"]).casefold())]
    return {"count": len(result), "rows": result}


def main():
    sampling = json.loads((ROOT / "data/prepared/sampling_manifest.json").read_text())
    result = {"schema_version": "1.0", "sampling": sampling, "runs": {}}
    for mode in ("baseline", "balanced"):
        out = ROOT / f"outputs/{mode}"
        rows = read_jsonl(out / "reviews.jsonl")
        metrics = json.loads((out / "metrics.json").read_text())
        emotions = json.loads((out / "emotion_metrics.json").read_text())
        classes = metrics["classes"]
        charts = {
            "star_distribution": [{"stars": i, "count": metrics["rating_distribution"][str(i)]} for i in range(1, 6)],
            "class_comparison": [{"class": c, "reference": metrics["per_class"][c]["support"], "predicted": metrics["per_class"][c]["predicted_count"]} for c in classes],
            "per_class_performance": [{"class": c, **metrics["per_class"][c]} for c in classes],
            "confusion_cells": [{"reference": c, "predicted": d, "count": metrics["confusion_matrix"][i][j]} for i, c in enumerate(classes) for j, d in enumerate(classes)],
            "emotion_comparison": [{"emotion": e, "llm": emotions["llm_distribution"][e], "nrc": emotions["nrc_distribution"][e]} for e in emotions["labels"]],
            "emotion_confusion_cells": [{"llm": e, "nrc": f, "count": emotions["matrix"][i][j]} for i, e in enumerate(emotions["labels"]) for j, f in enumerate(emotions["labels"])],
        }
        filters = {value: filter_reviews(rows, correctness=value)["count"] for value in ("all", "correct", "mismatched")}
        assert filters["all"] == metrics["count"] == filters["correct"] + filters["mismatched"]
        assert filters["correct"] == metrics["correct"]
        result["runs"][mode] = {"metrics": metrics, "emotion_metrics": emotions, "charts": charts, "reviews": rows,
                                  "filter_counts": filters, "run_manifest": json.loads((out / "run_manifest.json").read_text()),
                                  "lexicon_manifest": json.loads((out / "lexicon_manifest.json").read_text())}
        table_dir = ROOT / f"outputs/dashboard_ready/tables/{mode}"
        table_dir.mkdir(parents=True, exist_ok=True)
        for name, table in charts.items():
            with (table_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(table[0]))
                writer.writeheader()
                writer.writerows(table)
    result["population_star_distribution"] = [{"stars": i, "count": sampling["population_stars"][str(i)]} for i in range(1, 6)]
    result["comparison_caveat"] = "Baseline and balanced runs differ in samples, class definitions and prompts; their accuracy difference is not a causal estimate of sampling alone."
    write_json(ROOT / "outputs/dashboard_ready/dashboard_data.json", result)
    print("Prepared dashboard_data.json and chart CSVs")


if __name__ == "__main__":
    main()
