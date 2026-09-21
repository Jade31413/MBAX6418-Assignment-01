"""Offline regression checks for rating leakage, metrics, lexicon edges and filters."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from common import CLASSES, label
from classify import make_payload, parse_response, constrain_output
from score import evaluate
from add_emotions import derive, compare
from prepare_dashboard import filter_reviews


class PipelineTests(unittest.TestCase):
    def test_rating_boundaries(self):
        self.assertEqual([label(i) for i in range(1, 6)], ["NEGATIVE", "NEGATIVE", "NEUTRAL", "POSITIVE", "POSITIVE"])
        self.assertEqual(label(3, "binary"), "NEGATIVE")
        with self.assertRaises(ValueError):
            label(0)

    def test_rating_and_metadata_cannot_leak(self):
        row = {"title": "Example", "text": "Works", "rating": 1, "true_sentiment": "NEGATIVE", "user_id": "private"}
        config = {"model": "test"}
        a = make_payload(row, "prompt", config)
        row.update(rating=5, true_sentiment="POSITIVE", user_id="other")
        self.assertEqual(a, make_payload(row, "prompt", config))
        self.assertEqual(json.loads(a["messages"][1]["content"]), {"title": "Example", "text": "Works"})

    def test_reject_truncation_and_bad_labels(self):
        def raw(content, finish="stop"):
            return {"choices": [{"finish_reason": finish, "message": {"content": content}}]}
        for response in [raw('{"sentiment":"POSITIVE"}', "length"), raw('{"sentiment":"NEUTRAL"}'), raw('{"sentiment":"POSITIVE","extra":1}')]:
            with self.assertRaises(ValueError):
                parse_response(response, "smoke")
        self.assertEqual(parse_response(raw('{"sentiment":"POSITIVE"}'), "smoke"), {"sentiment": "POSITIVE"})

    def test_schema_recovery_preserves_model_inputs(self):
        original = make_payload({"title": "Nice", "text": "Boring card"}, "prompt", {"model": "test"})
        recovered = constrain_output(original, "balanced")
        self.assertEqual(recovered["messages"], original["messages"])
        self.assertEqual(original["response_format"], {"type": "json_object"})
        schema = recovered["response_format"]["json_schema"]["schema"]
        self.assertNotIn("disappointment", schema["properties"]["emotion"]["enum"])
        self.assertIn("sadness", schema["properties"]["emotion"]["enum"])
        self.assertEqual(schema["properties"]["sentiment"]["enum"], CLASSES)

    def test_metric_orientation_and_denominators(self):
        rows = [{"true_sentiment": t, "predicted_sentiment": p} for t, p in [
            ("NEGATIVE", "NEGATIVE"), ("NEGATIVE", "POSITIVE"), ("NEUTRAL", "POSITIVE"), ("POSITIVE", "POSITIVE")]]
        m = evaluate(rows, CLASSES)
        self.assertEqual(m["confusion_matrix"], [[1, 0, 1], [0, 0, 1], [0, 0, 1]])
        self.assertEqual(m["accuracy"], 0.5)
        self.assertEqual(m["balanced_accuracy"], 0.5)
        self.assertAlmostEqual(m["per_class"]["POSITIVE"]["precision"], 1/3)
        self.assertEqual(m["per_class"]["NEUTRAL"]["f1"], 0)
        self.assertAlmostEqual(m["macro_f1"], (2/3 + 0 + 0.5)/3)

    def test_empty_evaluation_fails(self):
        with self.assertRaises(ValueError):
            evaluate([], CLASSES)

    def test_nrc_zero_hit_is_not_arbitrary_emotion(self):
        r = derive("", "xyz", {"happy": {"joy"}})
        self.assertEqual(r["nrc_emotion"], "none")
        self.assertEqual(r["nrc_top_emotions"], [])
        self.assertFalse(r["nrc_tie"])

    def test_nrc_counts_and_ties(self):
        r = derive("HAPPY", "<b>happy</b> &amp; secure", {"happy": {"joy", "trust"}, "secure": {"trust"}})
        self.assertEqual((r["nrc_scores"]["joy"], r["nrc_scores"]["trust"]), (2, 3))
        self.assertEqual(r["nrc_emotion"], "trust")
        r = derive("", "happy", {"happy": {"trust", "joy"}})
        self.assertTrue(r["nrc_tie"])
        self.assertEqual(r["nrc_top_emotions"], ["joy", "trust"])
        self.assertEqual(r["nrc_emotion"], "joy")

    def test_filters_combine_and_empty_counts(self):
        rows = [
            {"title": "BAD", "text": "delivery", "correct": False, "true_sentiment": "NEGATIVE", "predicted_sentiment": "NEUTRAL", "emotion_agree": False},
            {"title": "good", "text": "gift", "correct": True, "true_sentiment": "POSITIVE", "predicted_sentiment": "POSITIVE", "emotion_agree": True}]
        self.assertEqual(filter_reviews(rows, correctness="mismatched", sentiment="NEGATIVE", query="bad")["count"], 1)
        self.assertEqual(filter_reviews(rows, correctness="correct", emotion_agreement="disagree")["count"], 0)
        self.assertEqual(filter_reviews(rows)["count"], 2)
        with self.assertRaises(ValueError):
            filter_reviews(rows, correctness="typo")

    def test_emotion_denominators_and_tie_aware_agreement(self):
        rows = []
        for text, llm in (("xyz", "none"), ("gift", "joy"), ("happy", "joy")):
            row = derive("", text, {"gift": {"anticipation", "joy"}, "happy": {"joy"}})
            row.update(llm_emotion=llm, review_id=text, emotion_agree=llm == row["nrc_emotion"])
            rows.append(row)
        m = compare(rows)
        self.assertEqual(m["agreement_count"], 2)
        self.assertEqual(m["matched_agreement_rate"], 0.5)
        self.assertEqual(m["unique_max_agreement_rate"], 1)
        self.assertEqual(m["top_set_agreement_rate_among_matched"], 1)
        self.assertEqual(m["nrc_no_match_count"], 1)
        self.assertEqual(m["nrc_tie_count"], 1)


if __name__ == "__main__":
    unittest.main()
