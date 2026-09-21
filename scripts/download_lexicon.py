"""Download the official lexicon for local educational use; excluded from Git."""
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile
from common import ROOT

URL = "https://saifmohammad.com/WebDocs/Lexicons/NRC-Emotion-Lexicon.zip"


if __name__ == "__main__":
    target = ROOT / "data/lexicon"
    target.mkdir(parents=True, exist_ok=True)
    archive = target / "NRC-Emotion-Lexicon.zip"
    urlretrieve(URL, archive)
    with ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith("__MACOSX"):
                continue
            if Path(name).name in ("NRC-Emotion-Lexicon-Wordlevel-v0.92.txt", "README.txt"):
                (target / Path(name).name).write_bytes(z.read(name))
    if not (target / "NRC-Emotion-Lexicon-Wordlevel-v0.92.txt").exists():
        raise SystemExit("Archive layout changed; inspect the official download")
    print("Downloaded for local use. Do not redistribute the lexicon; cite its authors and NRC.")
