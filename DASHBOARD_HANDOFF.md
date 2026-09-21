# Dashboard implementation and maintenance

The completed dashboard is `dashboard.html`. Open it directly in a browser; it works offline.
Edit `dashboard/template.html`, `dashboard/styles.css` and `dashboard/app.js`, then run
`python3 scripts/build_dashboard.py`. The `:root` CSS variables control the shared theme.
The full Python pipeline also regenerates the HTML. No frontend runtime dependencies are needed.

Use `outputs/dashboard_ready/dashboard_data.json` as the single source of truth.
The file contains both runs, all review details, scalar metrics, matrices, chart-ready
tables, filter counts, model settings, source provenance and NRC methods. Six CSV
tables per run are also available under `outputs/dashboard_ready/tables/`.

## Required views

- Run switch: initial 100-row binary run versus balanced 150-row three-class run.
- Headline metrics: count, accuracy, macro F1, balanced accuracy and majority baseline.
- Rating distribution: distinguish the whole dataset from the selected evaluation sample.
- Confusion matrix: **rows = rating reference; columns = model prediction**.
- Reference versus predicted class counts, and recall per class. Label recall correctly;
  do not call it precision or overall accuracy. All rates in JSON are fractions, not percentages.
- LLM/NRC emotion distributions and method agreement, including no-match and tie counts.
  Emotion agreement is not accuracy. `none` means no supported emotion, not neutral sentiment.
- Review table: ID, title, body, stars, reference/predicted sentiment, correctness,
  LLM/NRC emotions, eight NRC scores, matched terms, top-score ties and agreement.
- Filters: correct/mismatched/all, reference class, predicted class, emotion agreement,
  case-insensitive substring search in title/body, reset, and live row count.
  Combine filters with AND. Reference behavior is `scripts/prepare_dashboard.py:filter_reviews`.

## Contract and implementation details

- Schema version: `1.0`; `runs.baseline` and `runs.balanced` share a structure.
- `metrics.classes` defines matrix axis order; never hard-code three classes for the binary run.
- `charts` contains `star_distribution`, `class_comparison`, `per_class_performance`,
  `confusion_cells`, `emotion_comparison`, and `emotion_confusion_cells`.
- Do not recalculate rounded numbers or overwrite saved metrics in the browser.
- Render review strings as text, never untrusted HTML. If embedding JSON in HTML,
  escape `<` (including `</script>` sequences) before placing it in a script element.
- A self-contained HTML can embed this JSON and function without a server or network.
  There is no external API dependency at dashboard viewing time.
- Use accessible colors and labels, stable chart scales, a clear legend, deliberate fonts,
  and centralized theme colors that can be changed without changing the data.
- Show true zero values; keep nonzero chart marks visible without fabricating values.
  Avoid flex/layout shrinkage caused by long labels. Test narrow widths and long reviews.
- An empty filtered result must show 0 and an empty-state message, not stale rows.

## Browser acceptance checks

1. Reconcile every headline, chart total and matrix cell against the bundle in the browser.
2. Check run switching, all filter combinations, search, reset, empty results and live counts.
3. Preserve review IDs so every displayed claim can be traced to a saved raw response.
4. Test offline loading and small nonzero chart elements in a real browser.
5. Capture dashboard screenshots and add them to the final README.
6. Have the student check the evidence and rewrite the report's interpretations in their own words.

Run `node tests/dashboard.browser.cjs` with Playwright available to recheck the dashboard and
capture screenshots. The saved `outputs/browser_verification.json` records the exact HTML
hash, chart/metric reconciliation, 225 filter combinations, offline loading, mobile layout,
200% text enlargement and interaction checks. A changed HTML hash requires new browser QA.
The report generator only marks the UI verified when the tested hash matches the HTML.

Optional WebMCP tools are feature-detected; their contracts are checked with a test registry.
Native browser WebMCP availability is not required for ordinary use.

Steps 3, 4 and 7 now have implemented views and controls. Student review and GitHub/Canvas
submission are the remaining handoff steps. The repository is https://github.com/Jade31413/MBAX6418-Assignment-01.
