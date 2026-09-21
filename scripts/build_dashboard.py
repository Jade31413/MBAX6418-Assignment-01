"""Build a single offline HTML file from the verified analysis bundle."""
import json
from common import ROOT, file_hash, write_json


def main():
    data_path = ROOT / "outputs/dashboard_ready/dashboard_data.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    source = ROOT / "dashboard"
    template = (source / "template.html").read_text(encoding="utf-8")
    css = (source / "styles.css").read_text(encoding="utf-8")
    js = (source / "app.js").read_text(encoding="utf-8")
    # Prevent review text from closing its non-executable JSON script element.
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = template.replace("/*__CSS__*/", css).replace("/*__JS__*/", js).replace("__DATA__", encoded)
    out = ROOT / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    write_json(ROOT / "outputs/dashboard_build.json", {"output": "dashboard.html", "sha256": file_hash(out), "data_sha256": file_hash(data_path), "source_hashes": {name: file_hash(source / name) for name in ("template.html", "styles.css", "app.js")}, "external_dependencies": [], "rows": {k: len(v["reviews"]) for k, v in data["runs"].items()}})
    print(f"Built self-contained dashboard.html ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
