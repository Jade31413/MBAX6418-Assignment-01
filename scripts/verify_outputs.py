"""Audit real outputs independently; no network calls or regenerated predictions."""
from collections import Counter
import itertools
import json
from common import ROOT, CLASSES, digest, file_hash, label, read_jsonl, write_json
from classify import parse_response, constrain_output
from prepare_data import prepare
from prepare_dashboard import filter_reviews


def verify():
    bundle = json.loads((ROOT / "outputs/dashboard_ready/dashboard_data.json").read_text())
    original = json.loads((ROOT / "data/prepared/sampling_manifest.json").read_text())
    first, balanced, repeated = prepare()
    assert repeated == original, "Sampling is not reproducible"
    assert first == read_jsonl(ROOT / "data/prepared/baseline_100.jsonl")
    assert balanced == read_jsonl(ROOT / "data/prepared/balanced_150.jsonl")
    assert Counter(label(r["rating"]) for r in balanced) == {c: 50 for c in CLASSES}
    checks = []
    for mode, source in (("baseline", first), ("balanced", balanced)):
        out = ROOT / f"outputs/{mode}"
        rows = read_jsonl(out / "reviews.jsonl")
        raw = read_jsonl(out / "raw_responses.jsonl")
        lookup = {r["review_id"]: r for r in raw}
        assert len(rows) == len(source) == len(raw) == len(lookup)
        m = json.loads((out / "metrics.json").read_text())
        em = json.loads((out / "emotion_metrics.json").read_text())
        manifest = json.loads((out / "run_manifest.json").read_text())
        assert file_hash(ROOT / manifest["prompt_path"]) == manifest["prompt_sha256"]
        for row, original_row in zip(rows, source):
            saved = lookup[row["review_id"]]
            assert row["review_id"] == original_row["review_id"]
            assert saved["input_sha256"] == digest(original_row)
            request = saved["request"]
            assert json.loads(request["messages"][1]["content"]) == {k: original_row[k] for k in ("title", "text")}
            assert request["messages"][0]["content"] == (ROOT / manifest["prompt_path"]).read_text()
            for attempt in saved["attempts"]:
                assert attempt.get("request", request) in (request, constrain_output(request, mode))
            assert parse_response(saved["attempts"][-1]["response"], mode) == saved["prediction"]
            assert row["predicted_sentiment"] == saved["prediction"]["sentiment"]
            assert row["llm_emotion"] == saved["prediction"]["emotion"]
            assert row["true_sentiment"] == label(original_row["rating"], "binary" if mode == "baseline" else "three_class")
            assert row["correct"] == (row["true_sentiment"] == row["predicted_sentiment"])
        assert m["correct"] == sum(r["correct"] for r in rows)
        assert m["accuracy"] == m["correct"] / len(rows)
        assert m["mismatch_ids"] == [r["review_id"] for r in rows if not r["correct"]]
        for i, c in enumerate(m["classes"]):
            for j, d in enumerate(m["classes"]):
                assert m["confusion_matrix"][i][j] == sum(r["true_sentiment"] == c and r["predicted_sentiment"] == d for r in rows)
            tp = sum(r["true_sentiment"] == c and r["predicted_sentiment"] == c for r in rows)
            support = sum(r["true_sentiment"] == c for r in rows)
            predicted = sum(r["predicted_sentiment"] == c for r in rows)
            assert m["per_class"][c]["recall"] == (tp / support if support else 0)
            assert m["per_class"][c]["precision"] == (tp / predicted if predicted else 0)
        assert em["agreement_count"] == sum(r["llm_emotion"] == r["nrc_emotion"] for r in rows)
        assert sum(map(sum, em["matrix"])) == len(rows)
        for i, c in enumerate(em["labels"]):
            for j, d in enumerate(em["labels"]):
                assert em["matrix"][i][j] == sum(r["llm_emotion"] == c and r["nrc_emotion"] == d for r in rows)
        for correctness, cls, predicted in itertools.product(("all", "correct", "mismatched"), [None] + m["classes"], [None] + m["classes"]):
            filtered = filter_reviews(rows, correctness=correctness, sentiment=cls, predicted=predicted)
            expected = sum((correctness == "all" or r["correct"] == (correctness == "correct")) and (cls is None or r["true_sentiment"] == cls) and (predicted is None or r["predicted_sentiment"] == predicted) for r in rows)
            assert filtered["count"] == expected == len(filtered["rows"])
        data = bundle["runs"][mode]
        assert data["reviews"] == rows and data["metrics"] == m and data["emotion_metrics"] == em
        assert sum(x["count"] for x in data["charts"]["confusion_cells"]) == len(rows)
        assert sum(x["count"] for x in data["charts"]["star_distribution"]) == len(rows)
        assert sum(x["reference"] for x in data["charts"]["class_comparison"]) == len(rows)
        assert sum(x["predicted"] for x in data["charts"]["class_comparison"]) == len(rows)
        checks.append({"run": mode, "rows": len(rows), "status": "passed", "checks": ["sample reproducibility", "request allowlist/no rating metadata", "raw-response parsing", "reference labels", "confusion matrix", "precision/recall", "emotion matrix", "combined filter counts", "dashboard bundle reconciliation"]})
    browser_path = ROOT / "outputs/browser_verification.json"
    browser = json.loads(browser_path.read_text()) if browser_path.exists() else {}
    dashboard_path = ROOT / "dashboard.html"
    browser_status = "passed" if dashboard_path.exists() and browser.get("status") == "passed" and browser.get("dashboard_sha256") == file_hash(dashboard_path) else "pending: run tests/dashboard.browser.cjs against the current build"
    result = {"status": "passed", "runs": checks, "browser_validation": browser_status}
    write_json(ROOT / "outputs/verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    verify()
