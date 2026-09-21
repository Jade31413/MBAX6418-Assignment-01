"""Score saved responses, without model calls, against star-derived reference labels."""
import argparse
from collections import Counter
import json
from common import ROOT, CLASSES, label, read_jsonl, write_json, write_jsonl


def evaluate(rows, classes):
    matrix = [[0 for _ in classes] for _ in classes]
    for row in rows:
        matrix[classes.index(row["true_sentiment"])][classes.index(row["predicted_sentiment"])] += 1
    n = len(rows)
    if not n:
        raise ValueError("Cannot evaluate an empty sample")
    per_class = {}
    for i, cls in enumerate(classes):
        tp, support, predicted = matrix[i][i], sum(matrix[i]), sum(r[i] for r in matrix)
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        per_class[cls] = {"support": support, "predicted_count": predicted, "true_positive": tp,
                          "precision": precision, "recall": recall,
                          "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    correct = sum(matrix[i][i] for i in range(len(classes)))
    supported = [v["recall"] for v in per_class.values() if v["support"]]
    return {"count": n, "correct": correct, "incorrect": n - correct, "accuracy": correct / n,
            "balanced_accuracy": sum(supported) / len(supported),
            "macro_f1": sum(v["f1"] for v in per_class.values()) / len(classes),
            "weighted_f1": sum(v["f1"] * v["support"] for v in per_class.values()) / n,
            "majority_baseline_accuracy": max(v["support"] for v in per_class.values()) / n,
            "classes": classes, "confusion_matrix": matrix, "matrix_orientation": "rows=rating reference, columns=model prediction",
            "per_class": per_class, "zero_division_policy": "precision/recall/F1 are 0 when their denominator is 0; balanced accuracy averages supported classes only"}


def score_run(mode):
    name = "baseline_100" if mode == "baseline" else "balanced_150"
    source = read_jsonl(ROOT / f"data/prepared/{name}.jsonl")
    raw = read_jsonl(ROOT / f"outputs/{mode}/raw_responses.jsonl")
    predictions = {r["review_id"]: r["prediction"] for r in raw}
    if len(predictions) != len(raw) or set(predictions) != {r["review_id"] for r in source}:
        raise ValueError("Missing, duplicate, or unexpected predictions: complete classification before scoring")
    rows = []
    for record in source:
        row = dict(record)
        pred = predictions[row["review_id"]]
        row.update(true_sentiment=label(row["rating"], "binary" if mode == "baseline" else "three_class"),
                   predicted_sentiment=pred["sentiment"], llm_emotion=pred["emotion"])
        row["correct"] = row["true_sentiment"] == row["predicted_sentiment"]
        rows.append(row)
    classes = ["NEGATIVE", "POSITIVE"] if mode == "baseline" else CLASSES
    metrics = evaluate(rows, classes)
    metrics["rating_distribution"] = {str(star): sum(r["rating"] == star for r in rows) for star in range(1, 6)}
    metrics["mismatch_ids"] = [r["review_id"] for r in rows if not r["correct"]]
    write_jsonl(ROOT / f"outputs/{mode}/predictions.jsonl", rows)
    write_jsonl(ROOT / f"outputs/{mode}/mismatches.jsonl", [r for r in rows if not r["correct"]])
    write_json(ROOT / f"outputs/{mode}/metrics.json", metrics)
    print(f"{mode}: {metrics['correct']}/{metrics['count']} correct; accuracy={metrics['accuracy']:.4f}; macro F1={metrics['macro_f1']:.4f}")
    return metrics


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["baseline", "balanced"])
    score_run(p.parse_args().mode)
