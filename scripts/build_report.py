"""Generate the evidence draft directly from saved outputs (no invented metrics)."""
import json
from common import ROOT, read_jsonl, file_hash


def pct(v):
    return "n/a" if v is None else f"{v:.2%}"


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"] + ["| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in rows])


def main():
    data = json.loads((ROOT / "outputs/dashboard_ready/dashboard_data.json").read_text())
    base, bal = data["runs"]["baseline"], data["runs"]["balanced"]
    bm, tm, em = base["metrics"], bal["metrics"], bal["emotion_metrics"]
    sampling = data["sampling"]
    classes = tm["classes"]
    matrix = tm["confusion_matrix"]
    browser_path = ROOT / "outputs/browser_verification.json"
    browser = json.loads(browser_path.read_text()) if browser_path.exists() else {}
    html_path = ROOT / "dashboard.html"
    ui_verified = html_path.exists() and browser.get("status") == "passed" and browser.get("dashboard_sha256") == file_hash(html_path)
    stage_status = "Dashboard and analysis completed and browser-verified; student review and Canvas submission remain pending." if ui_verified else "Analysis and dashboard generated; browser validation of this exact build is pending."
    screenshots = '''## Dashboard

Repository: [Jade31413/MBAX6418-Assignment-01](https://github.com/Jade31413/MBAX6418-Assignment-01).

Open [dashboard.html](dashboard.html) locally in a browser. The complete dashboard is one
self-contained file with no CDN, server, API key or internet connection required.
GitHub normally displays HTML as source; download the file and open it locally to use it.

![Balanced-run overview with accuracy, confusion matrix and per-class recall](screenshots/dashboard-overview.png)

![LLM and NRC emotion comparison, including ties and no-match cases](screenshots/dashboard-emotions.png)

![Review detail showing complete text, model prediction and NRC evidence](screenshots/dashboard-review-detail.png)

Switch between the balanced and first-100 runs; click any confusion-matrix cell to inspect
its reviews. Search or combine correctness, reference, prediction and emotion-agreement
filters. Review titles open the full text, emotion scores and matched words. Charts remain
scoped to the selected run while review filters change only the table.
''' if ui_verified else "## Dashboard\n\nOpen `dashboard.html` locally. Run browser QA before using screenshots or submitting.\n"
    overview = table(["Run", "Reviews", "Accuracy", "Balanced accuracy", "Macro F1", "Always-majority baseline"], [
        [name, r["count"], pct(r["accuracy"]), pct(r["balanced_accuracy"]), f"{r['macro_f1']:.4f}", pct(r["majority_baseline_accuracy"])]
        for name, r in (("Sequential binary", bm), ("Balanced three-class", tm))])
    confusion = table(["Rating reference / predicted"] + classes, [[c] + matrix[i] for i, c in enumerate(classes)])
    class_table = table(["Class", "Support", "Predicted", "Precision", "Recall", "F1"], [[c, p["support"], p["predicted_count"], pct(p["precision"]), pct(p["recall"]), f"{p['f1']:.4f}"] for c, p in tm["per_class"].items()])
    neutral = matrix[classes.index("NEUTRAL")]
    directions = sorted([(matrix[i][j], c, d) for i, c in enumerate(classes) for j, d in enumerate(classes) if i != j], reverse=True)
    errors = "\n".join(f"- {c} → {d}: **{n}** reviews." for n, c, d in directions)
    mismatches = [r for r in bal["reviews"] if not r["correct"]]
    emotion_examples = [r for r in bal["reviews"] if not r["emotion_agree"]]
    example_table = table(["ID", "Stars", "Reference → predicted", "Title", "Text excerpt (first 220 chars)"], [[r["review_id"], int(r["rating"]), r["true_sentiment"] + " → " + r["predicted_sentiment"], r["title"], r["text"][:220]] for r in mismatches[:5]])
    emotion_table = table(["ID", "LLM", "NRC", "NRC tied maxima", "Matched terms"], [[r["review_id"], r["llm_emotion"], r["nrc_emotion"], ", ".join(r["nrc_top_emotions"]) or "none", ", ".join(f"{w} ({n})" for w, n in r["nrc_matched_words"].items())] for r in emotion_examples[:5]])
    content = f'''# Amazon Gift Cards: Sentiment and Emotion Analysis

**Status: {stage_status}**
This is an agent-generated evidence draft. The student must check the saved outputs and revise
the interpretations in their own words before submission.

{screenshots}

## Scope and reproducibility

We use the [Amazon Reviews '23 dataset](https://amazon-reviews-2023.github.io/),
Gift Cards review category, collected by the McAuley Lab at UC San Diego.
[Download the source data]({sampling['source_url']}).
The local file contains **{sampling['population_size']:,}** reviews; **{sampling['population_classes']['POSITIVE']:,}**
are rated 4–5 stars ({pct(sampling['population_classes']['POSITIVE']/sampling['population_size'])}).
See [sampling manifest](data/prepared/sampling_manifest.json) for full population counts,
the source SHA-256, selected row IDs and the seed (**{sampling['seed']}**).

The binary baseline uses the first 100 rows, with 4–5 stars positive and 1–3 stars negative.
The final run uses a uniform reservoir sample of 50 reviews per reference class from the
entire file: 1–2 negative, 3 neutral, 4–5 positive. Sampling is without replacement within
each class, using independent fixed random streams; {len(sampling['sample_overlap'])} review IDs overlap the two runs.
The initial four smoke checks use synthetic examples, not evaluation data.

The course endpoint is `http://dobolyi.com:9001/v1`, model
`{bal['run_manifest']['config']['model']}`. Python uses OpenAI-compatible Chat Completions,
temperature 0, top-p 1, seed 6418, JSON output and disabled thinking. Only title and text
are sent to the model; numeric rating and other metadata remain local. Titles may naturally
contain words such as “Five Stars”; supplied title text is retained as instructed.
Prompts handle conflicting title/body, short reviews, negation and mixed evaluations.
The sentiment-only prompt is spot-checked, then extended to emotion for the 100-row run.
Each prediction's exact request, raw response, timestamps, attempts and model fingerprint
are retained in `outputs/<run>/raw_responses.jsonl`. Secrets are never recorded there.
When an output violates the allowed labels, a retry constrains the same prompt and review
with a strict JSON Schema enum. The record's top-level request is the initial request;
attempt-level requests record any schema-constrained retry. Predictions are never manually relabeled.

Fixed inputs/settings do not guarantee identical future outputs from a shared model server.
Recomputing metrics from the saved raw responses is deterministic; fresh inference may vary.
The runner resumes only missing rows and refuses to mix changed inputs or prompts with an existing run.

## What the two runs show

{overview}

The first batch has {bm['per_class']['POSITIVE']['support']} positive and {bm['per_class']['NEGATIVE']['support']} negative
reference labels. Its {pct(bm['accuracy'])} accuracy exceeds the always-positive baseline of
{pct(bm['majority_baseline_accuracy'])}, but the dominant positive class heavily influences that headline.
Negative recall is {pct(bm['per_class']['NEGATIVE']['recall'])}, compared with
{pct(bm['per_class']['POSITIVE']['recall'])} for positive reviews. This is evidence of performance
on this small sequential sample, not a population-wide estimate.

With equal class support, majority guessing falls to {pct(tm['majority_baseline_accuracy'])},
and the neutral class becomes visible. The three-class run gets {tm['correct']}/{tm['count']} correct.
**Both the sampling and the task change** (two labels become three, with a different prompt).
The accuracy difference cannot be attributed solely to balancing.

## Where mistakes go

Rows are rating-derived reference labels; columns are model predictions.

{confusion}

{class_table}

Of 50 three-star reviews, **{neutral[1]}** receive NEUTRAL, **{neutral[0]}** NEGATIVE and
**{neutral[2]}** POSITIVE. The observed neutral behavior is described by these counts,
rather than assuming in advance that neutral must collapse into one other class.

{errors}

Example mismatches (selection: first five in source-line order; full text is in the saved review file):

{example_table}

The assignment uses ratings as the evaluation reference. A text/rating mismatch does not always
mean the text interpretation is unreasonable: in the binary baseline, `gift_cards:99` says
“Very easy to use. I wish I knew about it earlier” but has three stars; it is negative under the
binary rating rule and the model calls it positive. Conversely, `gift_cards:18` has five stars
but describes a repeatedly missing gift note; the model calls it negative.
These examples illustrate a limitation of rating-derived reference labels, not grounds for
changing labels after seeing predictions.

## LLM versus NRC emotions

We use the [NRC Word-Emotion Association Lexicon (EmoLex)](https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm),
version 0.92, created by Saif M. Mohammad and Peter D. Turney at the National Research Council Canada.
Reference: Mohammad & Turney (2013), *Crowdsourcing a Word–Emotion Association Lexicon*,
Computational Intelligence, 29(3), 436–465.

The word-list method lowercases and tokenizes title plus body, sums matching token occurrences
over eight emotions, and selects the highest score. Repeated words count repeatedly. Ties use
alphabetical order, while retaining all tied labels. Zero emotional matches produce `none`.
The LLM can also use `none` when no emotion is supported. This is an abstention category,
not a ninth NRC emotion. Exact word matching has no stemming, negation or sarcasm handling.

In the balanced run:

- Primary-label agreement: **{em['agreement_count']}/{em['count']} ({pct(em['agreement_rate'])})**.
- No NRC emotional matches: **{em['nrc_no_match_count']}** reviews.
- Tied highest NRC scores: **{em['nrc_tie_count']}** reviews.
- Agreement among the **{em['matched_count']}** reviews with any NRC emotional match: **{pct(em['matched_agreement_rate'])}**.
- Agreement among the **{em['unique_max_count']}** reviews with a unique nonzero maximum: **{pct(em['unique_max_agreement_rate'])}**.
- LLM label in the NRC top-score set: **{em['top_set_agreement_count']}/{em['matched_count']} ({pct(em['top_set_agreement_rate_among_matched'])})** among matched reviews.

{emotion_table}

These are **agreement statistics, not emotion accuracy**: there are no human emotion labels.
NRC measures context-free word associations, while the LLM interprets the review in context.
Polysemy, generic gift vocabulary, negation, sparse matches and deterministic tie-breaking
are plausible sources of divergence. The per-review matched terms and eight scores make
those explanations inspectable; they do not prove which method is correct.

## Working files

- `prompts/`: sentiment-only, binary-plus-emotion and three-class-plus-emotion prompts.
- `scripts/classify.py`: resumable model runner with strict output validation.
- `scripts/score.py`: scoring, confusion matrices and mismatch records.
- `scripts/add_emotions.py`: independent NRC analysis with no model calls.
- `scripts/prepare_dashboard.py`: dashboard data generator and reference filtering logic.
- `scripts/build_dashboard.py`: generates the standalone HTML from `dashboard/` sources and saved data.
- `dashboard.html`: final offline dashboard; `dashboard/` contains its HTML, CSS and JavaScript sources.
- `screenshots/`: captured desktop, review-detail and mobile views.
- `outputs/baseline/` and `outputs/balanced/`: raw responses, predictions, enriched reviews,
  metrics, emotion metrics and manifests.
- [Dashboard data](outputs/dashboard_ready/dashboard_data.json): all records and chart series.
- `outputs/dashboard_ready/tables/`: chart CSVs for both runs.
- [Dashboard handoff](DASHBOARD_HANDOFF.md): data contract and future browser acceptance checks.
- [Verification](outputs/verification.json): sampling, request, metric, matrix and filter audits.

Browser verification of this build: **{'passed' if ui_verified else 'pending'}**.
See [browser verification](outputs/browser_verification.json) for exact-build checks of metrics,
chart values, all 225 class/result/emotion filter combinations across the two runs, pagination,
search, empty states, review details, mobile layout and 200% text enlargement. The offline
browser check records zero external requests and zero runtime errors when it passes.

## Run locally

Python 3.9+ standard library only; there are no pip dependencies. Run from this directory.

```sh
# Download the source if it is not already present:
curl -fL '{sampling['source_url']}' -o data/Gift_Cards.jsonl.gz
# Download NRC locally for educational use (do not redistribute it):
python3 scripts/download_lexicon.py
# Set COURSE_API_KEY in the environment using the course-provided credential.
# Optional: COURSE_BASE_URL and COURSE_MODEL; see .env.example.
# The scripts read environment variables, not .env files automatically.
python3 scripts/run_pipeline.py --classify
```

To rebuild analysis from saved responses with no model calls:

```sh
python3 scripts/run_pipeline.py
python3 -m unittest discover -s tests -v
```

Offline full verification still needs the local original data and NRC lexicon.
The delivered HTML and dashboard data bundle are self-contained. Existing successful model responses
are reused; to intentionally make a new run, archive its output directory first.

To regenerate just the HTML from the existing dashboard data:

```sh
python3 scripts/build_dashboard.py
```

The optional development browser check requires Node.js and Playwright (Chromium installed):
`node tests/dashboard.browser.cjs`. It opens the local HTML with networking disabled and
saves screenshots plus the verification record. `PLAYWRIGHT_MODULE` can point to an existing
Playwright installation. After browser checks, run `python3 scripts/verify_outputs.py` and
`python3 scripts/build_report.py` to refresh this report's verification status.
Theme colors are centralized at the start of `dashboard/styles.css`.

## Issues and workarounds

- The initial sandbox could not resolve the course host. A permitted external-network execution
  reached it; authenticated requests then confirmed the exact model from the assignment.
- Lexicon zero hits and ties require explicit policies. Recording abstentions, all maxima and
  alternate agreement denominators prevents arbitrary tie-breaking from being hidden.
- A shared service can fail individual requests. The runner preserves successful raw responses,
  logs failed attempts, retries transient failures and resumes missing rows. Incomplete runs
  are rejected by the scoring stage rather than silently reducing the denominator.
- One observed invalid response used `disappointment` instead of an allowed NRC-aligned
  emotion label. Identical unconstrained retries repeated the invalid label; schema-constrained
  retries address this output-contract failure while retaining the failed response evidence.
- Browser QA checks that small nonzero bars stay visible and that the star-distribution selector
  uses the correct population/sample denominator. Review-table filters do not silently change
  the headline chart denominators.
- Visual inspection found the navigation highlight could lag behind the section on screen;
  section-position tracking fixed it. Native review dialogs support Escape and restore focus.
- Review text is rendered as text, and embedded JSON escapes script-closing characters.
  The dashboard loads locally without requesting fonts, libraries or model services.

Before submission, personally review this draft and
publish the report/code/outputs to your own GitHub repository. Submit that URL in Canvas.
Exclude credentials, the large re-downloadable source and the non-redistributable NRC lexicon.
'''
    (ROOT / "README.md").write_text(content, encoding="utf-8")
    print("Generated README.md evidence draft from saved metrics")


if __name__ == "__main__":
    main()
