"""Resumable OpenAI-compatible model calls. Only title/text enter user messages."""
import argparse
import concurrent.futures
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from common import ROOT, CLASSES, EMOTIONS, digest, file_hash, read_jsonl, write_json


def make_payload(row, prompt, config):
    # Deliberate allowlist: never serialize the full row into the model request.
    return {
        "model": config["model"], "temperature": 0, "top_p": 1,
        "seed": 6418, "max_tokens": 512,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "system", "content": prompt},
                     {"role": "user", "content": json.dumps({k: row[k] for k in ("title", "text")}, ensure_ascii=False)}],
    }


def parse_response(response, mode):
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError(f"Incomplete completion: {choice.get('finish_reason')}")
    result = json.loads(choice["message"]["content"])
    expected = {"sentiment"} if mode == "smoke" else {"sentiment", "emotion"}
    if not isinstance(result, dict) or set(result) != expected:
        raise ValueError("Unexpected model output schema")
    allowed = CLASSES if mode == "balanced" else ["NEGATIVE", "POSITIVE"]
    if result["sentiment"] not in allowed:
        raise ValueError("Invalid sentiment label")
    if mode != "smoke" and result["emotion"] not in EMOTIONS + ["none"]:
        raise ValueError("Invalid emotion label")
    return result


def constrain_output(payload, mode):
    properties = {"sentiment": {"type": "string", "enum": CLASSES if mode == "balanced" else ["NEGATIVE", "POSITIVE"]}}
    if mode != "smoke":
        properties["emotion"] = {"type": "string", "enum": EMOTIONS + ["none"]}
    return {**payload, "response_format": {"type": "json_schema", "json_schema": {
        "name": "review_classification", "strict": True,
        "schema": {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}}}}


def call_one(row, prompt, config, key, mode):
    payload = make_payload(row, prompt, config)
    initial_payload = payload
    attempts = []
    for attempt in range(1, 4):
        raw = None
        start = time.monotonic()
        try:
            req = urllib.request.Request(config["base_url"] + "/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
            with urllib.request.urlopen(req, timeout=120) as response:
                raw = json.load(response)
            result = parse_response(raw, mode)
            attempts.append({"attempt": attempt, "seconds": round(time.monotonic() - start, 3), "request": payload, "response": raw})
            return {"review_id": row["review_id"], "input_sha256": digest(row), "request": initial_payload,
                    "prediction": result, "attempts": attempts,
                    "completed_utc": datetime.now(timezone.utc).isoformat()}
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError) as exc:
            attempts.append({"attempt": attempt, "error": str(exc), "request": payload, "response": raw})
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 401, 403, 404):
                break
            if isinstance(exc, (ValueError, KeyError, IndexError)):
                # Re-query the model with enforced enums; never manually relabel a prediction.
                payload = constrain_output(initial_payload, mode)
            if attempt < 3:
                time.sleep(attempt * 2)
    return {"review_id": row["review_id"], "error": "All attempts failed", "request": initial_payload, "attempts": attempts}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["smoke", "baseline", "balanced"])
    p.add_argument("--workers", type=int, default=2)
    args = p.parse_args()
    if not 1 <= args.workers <= 4:
        p.error("Use 1-4 workers for the shared course endpoint")
    source_name = {"smoke": "smoke", "baseline": "baseline_100", "balanced": "balanced_150"}[args.mode]
    prompt_name = {"smoke": "binary", "baseline": "binary_emotion", "balanced": "three_class_emotion"}[args.mode]
    source = ROOT / "data/prepared" / (source_name + ".jsonl")
    prompt_path = ROOT / "prompts" / (prompt_name + ".txt")
    prompt = prompt_path.read_text()
    rows = read_jsonl(source)
    config = {"model": os.environ.get("COURSE_MODEL", "cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit"),
              "base_url": os.environ.get("COURSE_BASE_URL", "http://dobolyi.com:9001/v1").rstrip("/")}
    out = ROOT / "outputs" / args.mode
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"mode": args.mode, "config": config, "input_sha256": file_hash(source),
                "prompt_sha256": file_hash(prompt_path), "prompt_path": str(prompt_path.relative_to(ROOT)),
                "sample_count": len(rows), "settings": {k: v for k, v in make_payload(rows[0], prompt, config).items() if k != "messages"}}
    mp = out / "run_manifest.json"
    if mp.exists() and json.loads(mp.read_text()) != manifest:
        raise SystemExit("Run configuration/input changed: archive the existing output directory before rerunning")
    write_json(mp, manifest)
    raw_path = out / "raw_responses.jsonl"
    cached = read_jsonl(raw_path) if raw_path.exists() else []
    by_id = {r["review_id"]: r for r in cached}
    if len(by_id) != len(cached):
        raise SystemExit("Duplicate cached review IDs")
    for row in rows:
        if row["review_id"] in by_id:
            saved = by_id[row["review_id"]]
            if saved["input_sha256"] != digest(row) or saved["request"] != make_payload(row, prompt, config):
                raise SystemExit("Cached input/request mismatch")
            parse_response(saved["attempts"][-1]["response"], args.mode)
    pending = [r for r in rows if r["review_id"] not in by_id]
    if pending:
        key = os.environ.get("COURSE_API_KEY")
        if not key:
            raise SystemExit("Set COURSE_API_KEY in your environment; credentials are never written to outputs")
        failures = []
        with raw_path.open("a", encoding="utf-8") as f, concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(call_one, row, prompt, config, key, args.mode) for row in pending]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if "error" in result:
                    failures.append(result)
                    with (out / "failed_attempts.jsonl").open("a", encoding="utf-8") as errors:
                        errors.write(json.dumps(result, ensure_ascii=False) + "\n")
                else:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                    f.flush()
                    by_id[result["review_id"]] = result
                print(f"{args.mode}: {len(by_id)}/{len(rows)} saved; {len(failures)} failed", flush=True)
        if failures:
            write_json(out / "failures.json", failures)
            raise SystemExit("Incomplete run: see failures.json; rerun to retry missing rows")
    if set(by_id) != {r["review_id"] for r in rows}:
        raise SystemExit("Run output IDs do not match sample")
    if args.mode == "smoke":
        checks = [{"review_id": r["review_id"], "expected": r["expected"], "actual": by_id[r["review_id"]]["prediction"]["sentiment"]} for r in rows]
        write_json(out / "checks.json", checks)
        if any(c["expected"] != c["actual"] for c in checks):
            raise SystemExit("Smoke check failed; inspect before running batches")
    (out / "failures.json").unlink(missing_ok=True)
    print(f"Complete: {args.mode}, {len(by_id)} validated responses")


if __name__ == "__main__":
    main()
