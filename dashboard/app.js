(() => {
  'use strict';
  const DATA = JSON.parse(document.getElementById('analysis-data').textContent);
  const $ = id => document.getElementById(id);
  const pretty = s => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  const pct = (n, digits = 1) => n == null ? 'N/A' : (n * 100).toFixed(digits) + '%';
  const number = n => n.toLocaleString('en-US');
  const colors = {NEGATIVE: 'var(--negative)', NEUTRAL: 'var(--neutral)', POSITIVE: 'var(--positive)'};
  const state = {run: 'balanced', page: 1, pageSize: 15};
  let filtered = [], returnFocus;
  const current = () => DATA.runs[state.run];
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function clear(id) { const node = $(id); node.replaceChildren(); return node; }
  function fillTrack(value, max, color, minimum = false) {
    const track = el('div', null, 'track');
    const fill = el('div', null, 'fill');
    fill.style.setProperty('--width', (max ? value / max * 100 : 0) + '%');
    fill.style.setProperty('--color', color);
    if (minimum) fill.style.setProperty('--min', value ? '2px' : '0px');
    fill.dataset.value = value;
    track.append(fill);
    return track;
  }
  function simpleTable(headers, rows, className = 'mini-table') {
    const table = el('table', null, className), head = el('thead'), tr = el('tr');
    headers.forEach(h => { const th = el('th', h); th.scope = 'col'; tr.append(th); });
    head.append(tr); table.append(head);
    const body = el('tbody');
    rows.forEach(row => { const tr = el('tr'); row.forEach((v, i) => { const td = el(i ? 'td' : 'th', v); if (!i) td.scope = 'row'; tr.append(td); }); body.append(tr); });
    table.append(body); return table;
  }
  function renderSummary() {
    const m = current().metrics;
    const entries = [
      ['Accuracy', pct(m.accuracy, 2), `${m.correct} of ${m.count} reviews correct`, 'accuracy'],
      ['Macro F1', m.macro_f1.toFixed(3), 'Each class carries equal weight', 'macro_f1'],
      ['Balanced accuracy', pct(m.balanced_accuracy, 2), 'Average recall across classes', 'balanced_accuracy'],
      ['Majority baseline', pct(m.majority_baseline_accuracy, 2), 'If every review got one label', 'majority_baseline_accuracy']
    ];
    const target = clear('metrics');
    entries.forEach(([label, value, sub, key], i) => {
      const node = el('article', null, 'metric' + (i === 0 ? ' primary' : ''));
      node.dataset.metric = key;
      node.append(el('div', label, 'label'), el('div', value, 'value'), el('div', sub, 'sub')); target.append(node);
    });
    const context = clear('run-context');
    (state.run === 'balanced' ? ['150 reviews', '50 per class', 'Seed 6418', '4–5 positive · 3 neutral · 1–2 negative'] : ['100 reviews', 'First rows in source order', '4–5 positive · 1–3 negative']).forEach(t => context.append(el('span', t)));
    const insight = clear('insight'); insight.append(el('span', '↳', 'insight-icon'));
    const text = el('div');
    if (state.run === 'balanced') {
      const i = m.classes.indexOf('NEUTRAL'), row = m.confusion_matrix[i];
      text.append(el('strong', 'Neutral is the blind spot. '), document.createTextNode(`${row[i]} of ${m.per_class.NEUTRAL.support} three-star reviews were recognized as neutral; ${row[0]} were called negative and ${row[2]} positive.`));
    } else {
      text.append(el('strong', 'High accuracy, uneven evidence. '), document.createTextNode(`${m.per_class.POSITIVE.support} of ${m.count} reviews are positive. Always guessing positive already scores ${pct(m.majority_baseline_accuracy, 0)}.`));
    }
    insight.append(text);
    const rows = Object.entries(DATA.runs).map(([key, r]) => [key === 'baseline' ? 'First 100 · binary' : 'Balanced 150 · three-class', r.metrics.count, pct(r.metrics.accuracy, 2), r.metrics.macro_f1.toFixed(3), pct(r.metrics.majority_baseline_accuracy, 2)]);
    clear('run-comparison').append(simpleTable(['Run', 'Reviews', 'Accuracy', 'Macro F1', 'Majority baseline'], rows));
  }
  function renderConfusion() {
    const m = current().metrics, table = el('table', null, 'matrix');
    table.setAttribute('aria-label', 'Sentiment confusion matrix: reference rows, predicted columns');
    const thead = el('thead'), header = el('tr'); header.append(el('th', 'Reference ↓'));
    m.classes.forEach(c => { const th = el('th', pretty(c)); th.scope = 'col'; header.append(th); }); thead.append(header); table.append(thead);
    const body = el('tbody');
    m.classes.forEach((c, i) => {
      const row = el('tr'), th = el('th', pretty(c)); th.scope = 'row'; row.append(th);
      m.classes.forEach((d, j) => {
        const n = m.confusion_matrix[i][j], td = el('td'), button = el('button', String(n));
        button.type = 'button'; button.dataset.reference = c; button.dataset.predicted = d; button.dataset.count = n;
        const strength = n / m.per_class[c].support;
        button.style.setProperty('--cell-bg', i === j ? `rgba(8,126,112,${.08 + strength * .72})` : `rgba(187,70,86,${n ? .06 + strength * .4 : .025})`);
        button.style.setProperty('--cell-ink', i === j && strength > .65 ? '#fff' : (i === j ? '#076354' : '#903d4b'));
        button.setAttribute('aria-label', `${pretty(c)} reference, ${pretty(d)} prediction: ${n} reviews`);
        button.append(el('small', pct(strength, 0) + ' of class'));
        button.addEventListener('click', () => { resetFilters(false); $('reference').value = c; $('predicted').value = d; renderReviews(); $('reviews').scrollIntoView({behavior: 'auto'}); $('reference').focus({preventScroll: true}); });
        td.append(button); row.append(td);
      }); body.append(row);
    }); table.append(body); clear('confusion').append(table);
  }
  function renderRecall() {
    const m = current().metrics, target = clear('recall');
    m.classes.forEach(c => {
      const p = m.per_class[c], row = el('div', null, 'recall-row'); row.dataset.class = c;
      const header = el('header'), label = el('span', pretty(c)); label.append(el('small', `${p.true_positive} / ${p.support}`));
      header.append(label, el('strong', pct(p.recall, 0))); row.append(header, fillTrack(p.recall, 1, colors[c])); target.append(row);
    });
    clear('class-metrics').append(simpleTable(['Class', 'Precision', 'Recall', 'F1'], m.classes.map(c => { const p = m.per_class[c]; return [pretty(c), pct(p.precision), pct(p.recall), p.f1.toFixed(3)]; })));
  }
  function renderStars() {
    const population = $('distribution').value === 'population';
    const series = population ? DATA.population_star_distribution : current().charts.star_distribution;
    const total = series.reduce((a, x) => a + x.count, 0), max = Math.max(...series.map(x => x.count));
    $('rating-caption').textContent = `${number(total)} reviews · ${population ? 'entire Gift Cards dataset' : 'selected evaluation sample'}`;
    const target = clear('stars');
    series.forEach(x => { const row = el('div', null, 'bar-row'); row.dataset.stars = x.stars; row.dataset.count = x.count;
      row.append(el('span', x.stars + ' ★'), fillTrack(x.count, max, x.stars < 3 ? 'var(--negative)' : x.stars === 3 ? 'var(--neutral)' : 'var(--positive)', true), el('span', number(x.count) + ' · ' + pct(x.count / total, 0), 'bar-value')); target.append(row); });
  }
  function pairedBars(a, b, max, colorA, colorB) {
    const pair = el('div', null, 'pair');
    [[a, colorA], [b, colorB]].forEach(([value, color]) => { const line = el('div', null, 'pair-line'); line.append(fillTrack(value, max, color), el('span', String(value))); pair.append(line); });
    return pair;
  }
  function renderComparison() {
    const series = current().charts.class_comparison, max = Math.max(...series.flatMap(x => [x.reference, x.predicted]));
    const target = clear('comparison');
    series.forEach(x => { const row = el('div', null, 'group-row'); row.dataset.class = x.class;
      row.append(el('span', pretty(x.class)), pairedBars(x.reference, x.predicted, max, '#bacad7', 'var(--accent)')); target.append(row); });
  }
  function renderEmotions() {
    const e = current().emotion_metrics;
    const agreement = clear('agreement'); agreement.append(document.createTextNode(pct(e.agreement_rate, 0)), el('small', `${e.agreement_count} of ${e.count} reviews`));
    const stats = clear('emotion-stats');
    [['No NRC word matches', String(e.nrc_no_match_count)], ['Tied NRC maxima', String(e.nrc_tie_count)], ['Agreement · matched only', pct(e.matched_agreement_rate)], ['Agreement · unique maxima', pct(e.unique_max_agreement_rate)], ['LLM in NRC top set¹', pct(e.top_set_agreement_rate_among_matched)]].forEach(([label, value]) => { const line = el('div', null, 'stat-line'); line.append(el('span', label), el('strong', value)); stats.append(line); });
    stats.append(el('p', `¹ Among ${e.matched_count} reviews with a match. Unique-max agreement uses ${e.unique_max_count} reviews.`, 'hint'));
    const series = current().charts.emotion_comparison, max = Math.max(...series.flatMap(x => [x.llm, x.nrc])), target = clear('emotion-bars');
    series.forEach(x => { const row = el('div', null, 'emotion-row'); row.dataset.emotion = x.emotion; row.append(el('span', x.emotion), pairedBars(x.llm, x.nrc, max, 'var(--accent)', 'var(--nrc)')); target.append(row); });
    const matrix = simpleTable(['LLM ↓ / NRC →', ...e.labels.map(pretty)], e.labels.map((label, i) => [pretty(label), ...e.matrix[i]]), 'emotion-matrix');
    matrix.setAttribute('aria-label', 'Emotion comparison matrix: LLM rows, NRC columns');
    matrix.querySelectorAll('tbody td').forEach(td => td.style.setProperty('--cell-bg', `rgba(113,98,200,${Number(td.textContent) ? .05 + Number(td.textContent) / e.count : 0})`));
    clear('emotion-matrix').append(matrix);
  }
  function classOptions(id) {
    const target = clear(id); const all = el('option', 'All classes'); all.value = ''; target.append(all);
    current().metrics.classes.forEach(c => { const option = el('option', pretty(c)); option.value = c; target.append(option); });
  }
  function resetFilters(render = true) {
    $('search').value = ''; $('correctness').value = 'all'; $('reference').value = ''; $('predicted').value = ''; $('emotion-filter').value = 'all'; state.page = 1;
    if (render) renderReviews();
  }
  function matchingRows() {
    const query = $('search').value.trim().toLocaleLowerCase('en-US');
    return current().reviews.filter(r =>
      ($('correctness').value === 'all' || r.correct === ($('correctness').value === 'correct')) &&
      (!$('reference').value || r.true_sentiment === $('reference').value) &&
      (!$('predicted').value || r.predicted_sentiment === $('predicted').value) &&
      ($('emotion-filter').value === 'all' || r.emotion_agree === ($('emotion-filter').value === 'agree')) &&
      (!query || (r.title + ' ' + r.text).toLocaleLowerCase('en-US').includes(query)));
  }
  function badge(value) { return el('span', pretty(value), 'badge ' + value); }
  function plainReview(text) {
    // Decode entities without ever creating review-supplied elements or resource URLs.
    const decoder = document.createElement('textarea');
    decoder.innerHTML = text.replace(/<br\s*\/?\s*>/gi, '\n').replace(/<[^>]*>/g, '').replace(/</g, '&lt;');
    return decoder.value;
  }
  function renderReviews() {
    filtered = matchingRows(); const pages = Math.max(1, Math.ceil(filtered.length / state.pageSize)); state.page = Math.min(state.page, pages);
    $('result-count').textContent = `${filtered.length} of ${current().reviews.length} reviews`;
    const target = clear('review-rows');
    const start = (state.page - 1) * state.pageSize;
    filtered.slice(start, start + state.pageSize).forEach(r => {
      const tr = el('tr'); tr.dataset.reviewId = r.review_id;
      const first = el('td'), title = el('button', r.title || '(Untitled review)', 'review-title'); title.type = 'button';
      title.setAttribute('aria-label', 'Open review: ' + (r.title || r.review_id));
      title.addEventListener('click', () => openReview(r, title));
      first.append(title, el('span', plainReview(r.text), 'snippet'));
      const reference = el('td'), prediction = el('td'); reference.append(badge(r.true_sentiment)); prediction.append(badge(r.predicted_sentiment));
      const result = el('td'); result.append(el('span', r.correct ? '✓ Correct' : '≠ Mismatch', 'result ' + (r.correct ? 'yes' : 'no')));
      const emotion = el('td', pretty(r.llm_emotion), 'emotions-cell'); emotion.append(el('span', pretty(r.nrc_emotion) + (r.nrc_tie ? ' · tied' : '')));
      tr.append(first, el('td', r.rating + ' ★'), reference, prediction, result, emotion); target.append(tr);
    });
    $('empty').hidden = filtered.length > 0;
    $('page-label').textContent = filtered.length ? `${start + 1}–${Math.min(start + state.pageSize, filtered.length)} of ${filtered.length} · Page ${state.page} of ${pages}` : '0 reviews';
    $('previous').disabled = state.page === 1; $('next').disabled = state.page >= pages;
  }
  function openReview(r, trigger) {
    returnFocus = trigger;
    $('detail-id').textContent = `${r.review_id} · Source row ${number(r.source_line)}`;
    $('detail-title').textContent = r.title || '(Untitled review)';
    const labels = clear('detail-labels'); labels.append(el('span', `${r.rating} stars · Reference`), badge(r.true_sentiment), el('span', 'Prediction'), badge(r.predicted_sentiment));
    $('detail-text').textContent = plainReview(r.text);
    $('detail-emotions').textContent = `LLM: ${pretty(r.llm_emotion)} · NRC: ${pretty(r.nrc_emotion)} · ${r.emotion_agree ? 'Agree' : 'Disagree'}. ` + (r.nrc_no_match ? 'No NRC emotional words matched.' : r.nrc_tie ? `Tied maxima: ${r.nrc_top_emotions.join(', ')}. Alphabetical tie-break applied.` : 'Unique highest NRC score.');
    const scores = clear('detail-scores'), max = Math.max(...Object.values(r.nrc_scores), 1);
    Object.entries(r.nrc_scores).forEach(([emotion, count]) => { const row = el('div', null, 'bar-row'); row.append(el('span', pretty(emotion)), fillTrack(count, max, 'var(--nrc)'), el('span', String(count))); scores.append(row); });
    $('detail-words').textContent = 'Matched words: ' + (Object.entries(r.nrc_matched_words).map(([w, n]) => `${w} ×${n}`).join(', ') || 'none') + ` · ${r.nrc_matched_token_count}/${r.nrc_token_count} tokens matched.`;
    $('detail-meta').textContent = `Product: ${r.asin} · ${r.verified_purchase ? 'Verified purchase' : 'Not marked verified'} · Helpful votes: ${r.helpful_vote}`;
    $('review-dialog').showModal();
  }
  function renderProvenance() {
    const run = current().run_manifest, list = el('dl', null, 'provenance-list');
    [['Model', run.config.model], ['Run', state.run], ['Source SHA-256', DATA.sampling.source_sha256], ['Prompt SHA-256', run.prompt_sha256], ['Prompt file', run.prompt_path], ['Model settings', `Temperature ${run.settings.temperature}; top-p ${run.settings.top_p}; seed ${run.settings.seed}. Strict output validation and schema-constrained retries.`], ['NRC tie policy', current().lexicon_manifest.tie_policy]].forEach(([key, value]) => list.append(el('dt', key), el('dd', value)));
    clear('provenance').append(list);
  }
  function renderRun() {
    renderSummary(); renderConfusion(); renderRecall(); renderStars(); renderComparison(); renderEmotions(); renderProvenance();
    classOptions('reference'); classOptions('predicted'); resetFilters();
  }
  $('run').addEventListener('change', () => { state.run = $('run').value; renderRun(); });
  $('distribution').addEventListener('change', renderStars);
  ['correctness', 'reference', 'predicted', 'emotion-filter'].forEach(id => $(id).addEventListener('change', () => { state.page = 1; renderReviews(); }));
  $('search').addEventListener('input', () => { state.page = 1; renderReviews(); });
  $('reset').addEventListener('click', () => resetFilters());
  $('previous').addEventListener('click', () => { state.page--; renderReviews(); });
  $('next').addEventListener('click', () => { state.page++; renderReviews(); });
  $('close-dialog').addEventListener('click', () => $('review-dialog').close());
  $('review-dialog').addEventListener('close', () => { if (returnFocus?.isConnected) returnFocus.focus({preventScroll: true}); });
  $('review-dialog').addEventListener('click', event => { if (event.target === $('review-dialog')) { const b = $('review-dialog').getBoundingClientRect(); if (event.clientX < b.left || event.clientX > b.right || event.clientY < b.top || event.clientY > b.bottom) $('review-dialog').close(); } });
  const navigation = [...document.querySelectorAll('nav a')];
  const sections = [...document.querySelectorAll('main section')];
  let navigationFrame;
  function updateNavigation() {
    const visible = sections.filter(section => section.getBoundingClientRect().top <= innerHeight * .35);
    const id = (visible[visible.length - 1] || sections[0]).id;
    navigation.forEach(a => { const active = a.hash === '#' + id; a.classList.toggle('active', active); if (active) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current'); });
    navigationFrame = null;
  }
  window.addEventListener('scroll', () => { if (!navigationFrame) navigationFrame = requestAnimationFrame(updateNavigation); }, {passive: true});
  renderRun();
  updateNavigation();
  // Optional browser-native tools reuse visible controls; ordinary browsers need no polyfill.
  if (document.modelContext?.registerTool) {
    const controller = new AbortController(); window.addEventListener('pagehide', () => controller.abort(), {once: true});
    const tools = [{name: 'get_review_analysis', description: 'Read the selected review evaluation metrics.', inputSchema: {type: 'object', properties: {}, additionalProperties: false}, annotations: {readOnlyHint: true}, execute: () => ({run: state.run, metrics: current().metrics, emotion_metrics: current().emotion_metrics})},
      {name: 'filter_review_analysis', description: 'Set the visible run and review filters and return the matching review count.', inputSchema: {type: 'object', properties: {run: {type: 'string', enum: ['balanced', 'baseline']}, result: {type: 'string', enum: ['all', 'correct', 'mismatched']}, reference: {type: 'string', enum: ['', 'NEGATIVE', 'NEUTRAL', 'POSITIVE']}, predicted: {type: 'string', enum: ['', 'NEGATIVE', 'NEUTRAL', 'POSITIVE']}, emotion_agreement: {type: 'string', enum: ['all', 'agree', 'disagree']}, search: {type: 'string'}}, additionalProperties: false}, annotations: {readOnlyHint: false, untrustedContentHint: true}, execute: input => {
        if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Expected an object');
        const run = input.run ?? state.run, allowed = ['run', 'result', 'reference', 'predicted', 'emotion_agreement', 'search'];
        if (Object.keys(input).some(k => !allowed.includes(k)) || !Object.hasOwn(DATA.runs, run)) throw new Error('Invalid run or field');
        const options = {result: ['all', 'correct', 'mismatched'], reference: ['', ...DATA.runs[run].metrics.classes], predicted: ['', ...DATA.runs[run].metrics.classes], emotion_agreement: ['all', 'agree', 'disagree']};
        for (const [key, values] of Object.entries(options)) if (input[key] !== undefined && !values.includes(input[key])) throw new Error('Invalid ' + key);
        if (input.search !== undefined && typeof input.search !== 'string') throw new Error('Search must be a string');
        state.run = run; $('run').value = run; renderRun();
        for (const [key, id] of Object.entries({result: 'correctness', reference: 'reference', predicted: 'predicted', emotion_agreement: 'emotion-filter', search: 'search'})) if (input[key] !== undefined) $(id).value = input[key];
        renderReviews(); return {run: state.run, count: filtered.length, review_ids: filtered.map(r => r.review_id)};
      }}];
    for (const tool of tools) { try { Promise.resolve(document.modelContext.registerTool(tool, {signal: controller.signal})).catch(() => {}); } catch (_) { /* Optional API unavailable; visible controls remain functional. */ } }
  }
})();
