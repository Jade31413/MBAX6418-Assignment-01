"""Add NRC word-list emotions to existing predictions; never calls a model."""
import argparse
from collections import Counter
from html import unescape
import re
from common import ROOT, EMOTIONS, file_hash, read_jsonl, write_json, write_jsonl

LEXICON = ROOT / "data/lexicon/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt"


def load_lexicon(path):
    lexicon = {}
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) == 3 and parts[1] in EMOTIONS and parts[2] in ("0", "1"):
                word, emotion, score = parts
                lexicon.setdefault(word, set())
                if score == "1":
                    lexicon[word].add(emotion)
    if len(lexicon) < 10000:
        raise ValueError("Expected the full official NRC English word-level lexicon")
    return lexicon


def derive(title, text, lexicon):
    # Count token occurrences (not unique words), with title and body equally weighted.
    plain = re.sub(r"<[^>]*>", " ", unescape(title + " " + text)).lower()
    tokens = re.findall(r"[a-z]+(?:'[a-z]+)?", plain)
    scores = {emotion: 0 for emotion in EMOTIONS}
    matched = Counter()
    for token in tokens:
        emotions = lexicon.get(token, set())
        if emotions:
            matched[token] += 1
            for emotion in emotions:
                scores[emotion] += 1
    maximum = max(scores.values())
    top = sorted(e for e, n in scores.items() if n == maximum) if maximum else []
    return {"nrc_emotion": top[0] if top else "none", "nrc_scores": scores,
            "nrc_top_emotions": top, "nrc_tie": len(top) > 1,
            "nrc_no_match": not top, "nrc_matched_words": dict(sorted(matched.items())),
            "nrc_token_count": len(tokens), "nrc_matched_token_count": sum(matched.values())}


def compare(rows):
    labels = EMOTIONS + ["none"]
    matrix = [[0 for _ in labels] for _ in labels]
    for row in rows:
        matrix[labels.index(row["llm_emotion"])][labels.index(row["nrc_emotion"])] += 1
    matched = [r for r in rows if not r["nrc_no_match"]]
    unique = [r for r in matched if not r["nrc_tie"]]
    agree = sum(r["emotion_agree"] for r in rows)
    return {"count": len(rows), "agreement_count": agree, "agreement_rate": agree / len(rows),
            "nrc_no_match_count": len(rows) - len(matched), "nrc_tie_count": sum(r["nrc_tie"] for r in rows),
            "matched_count": len(matched),
            "matched_agreement_rate": sum(r["emotion_agree"] for r in matched) / len(matched) if matched else None,
            "unique_max_count": len(unique),
            "unique_max_agreement_rate": sum(r["emotion_agree"] for r in unique) / len(unique) if unique else None,
            "top_set_agreement_count": sum(r["llm_emotion"] in r["nrc_top_emotions"] for r in matched),
            "top_set_agreement_rate_among_matched": sum(r["llm_emotion"] in r["nrc_top_emotions"] for r in matched) / len(matched) if matched else None,
            "labels": labels, "matrix": matrix, "matrix_orientation": "rows=LLM emotion, columns=NRC primary emotion",
            "llm_distribution": {e: sum(r["llm_emotion"] == e for r in rows) for e in labels},
            "nrc_distribution": {e: sum(r["nrc_emotion"] == e for r in rows) for e in labels},
            "disagreement_ids": [r["review_id"] for r in rows if not r["emotion_agree"]],
            "interpretation": "Agreement between two methods is not emotion accuracy; there are no human emotion labels."}


def enrich(mode):
    lexicon = load_lexicon(LEXICON)
    rows = read_jsonl(ROOT / f"outputs/{mode}/predictions.jsonl")
    for row in rows:
        row.update(derive(row["title"], row["text"], lexicon))
        row["emotion_agree"] = row["llm_emotion"] == row["nrc_emotion"]
    out = ROOT / f"outputs/{mode}"
    write_jsonl(out / "reviews.jsonl", rows)
    write_json(out / "emotion_metrics.json", compare(rows))
    write_json(out / "lexicon_manifest.json", {
        "name": "NRC Word-Emotion Association Lexicon", "version": "0.92", "word_count": len(lexicon),
        "authors": "Saif M. Mohammad and Peter D. Turney, National Research Council Canada",
        "source": "https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm", "sha256": file_hash(LEXICON),
        "method": "HTML-unescape and remove tags; lowercase ASCII word tokens including internal apostrophes; exact lookup; count occurrences; no stemming, lemmatization, negation or sarcasm handling.",
        "tie_policy": "Alphabetically first highest-scoring emotion; preserve all tied emotions and tie flag.",
        "no_match_policy": "none when all eight emotion scores are zero; none is an abstention, not an NRC category.",
        "license": "Local non-commercial educational use; do not redistribute the lexicon."})
    m = compare(rows)
    print(f"{mode}: emotion agreement {m['agreement_count']}/{m['count']}; no match {m['nrc_no_match_count']}; ties {m['nrc_tie_count']}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["baseline", "balanced"])
    enrich(p.parse_args().mode)
