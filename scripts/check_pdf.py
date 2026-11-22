"""Verify the rendered PDF: overfull boxes, margin overruns, Greek glyph survival.

Why this exists. The previous check claimed "no overfull boxes" on a build that
had six, because it never looked at a TeX log. scripts/render_paper.py drives
xelatex through pandoc, and pandoc runs the engine in a temp directory it then
deletes, so the .log carrying every "Overfull \\hbox" warning was thrown away
before anything could read it. A check that inspects only the finished PDF for
things it already expects to find will pass a document that is visibly broken.

So this script rebuilds the paper the long way round: pandoc to standalone
.tex, then xelatex directly into build/, which leaves the log on disk. Two
independent detectors then run against that build.

  1. Log parse. TeX's own measurement of how far each box exceeds \\hsize,
     in points. This is authoritative for the overrun magnitude, and it
     catches boxes whose content is clipped rather than drawn.
  2. Geometric scan. Every text span in the output PDF is compared against
     the right edge of the text block. This is authoritative for the page
     number, which the log only supports by inference.

Neither subsumes the other. The log reports overruns that the PDF renders
invisibly; the scan reports the true page and the offending text. Both must
be clean.

Exit status is nonzero if any overfull box exceeds FAIL_PT, if any span
crosses the margin by more than FAIL_PT, or if a Greek character present in
the source is missing from the render.

Usage:
    python scripts/check_pdf.py            # rebuild into build/ and check
    python scripts/check_pdf.py --no-build # check the committed PDF only
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SRC_MD = ROOT / "paper" / "pairs_stat_arb.md"
OUT_PDF = ROOT / "paper" / "pairs_stat_arb.pdf"
BUILD = ROOT / "build"

# Overruns at or below this are invisible in print and not worth a failure.
# TeX's own \hfuzz default is 0.1pt, which flags boxes nobody can see.
FAIL_PT = 5.0

# Letter paper at 1in margins, matching the geometry passed in render_paper.py.
PAGE_W_PT = 612.0
MARGIN_PT = 72.0
TEXT_RIGHT_PT = PAGE_W_PT - MARGIN_PT

OVERFULL_RE = re.compile(
    r"^Overfull \\([hv])box \((\d+(?:\.\d+)?)pt too (?:wide|high)\)"
    r"(?: in (?:paragraph|alignment) at lines (\d+)--(\d+))?"
)


def build_with_log() -> Path:
    """Render via pandoc -> .tex -> xelatex so the .log survives. Returns log path."""
    from render_paper import pandoc_cmd

    if shutil.which("pandoc") is None:
        sys.exit("ERROR: pandoc not on PATH")
    if shutil.which("xelatex") is None:
        sys.exit("ERROR: xelatex not on PATH")

    BUILD.mkdir(exist_ok=True)
    tex = BUILD / "paper.tex"

    # Reuse render_paper's exact option list so this build cannot drift from the
    # canonical one. Only the output target changes, plus -s for a standalone file.
    cmd = pandoc_cmd(tex) + ["-s"]
    subprocess.run(cmd, check=True, cwd=ROOT)

    # xelatex must run FROM build/, not from the repo root. Pandoc rewrites image
    # paths relative to the output file, so the .tex refers to ../figures/...;
    # running from the root resolves that one level above the repo and every
    # \includegraphics fails, which kills the PDF without killing the log.
    # Two passes: the first writes the .aux that fancyhdr needs.
    for _ in range(2):
        subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-file-line-error", tex.name],
            cwd=BUILD, capture_output=True,
        )
    log = BUILD / "paper.log"
    if not log.exists():
        sys.exit("ERROR: xelatex produced no log")
    return log


def assert_usable(pdf_path: Path, reference: Path) -> None:
    """A build that produced no pages must fail loudly, not be scanned silently.

    Every detector below reports "clean" on an empty PDF, so an unusable build
    would otherwise be indistinguishable from a perfect one. It is the exact
    failure this script was written to stop, so it is checked here first.
    """
    import fitz

    if not pdf_path.exists():
        sys.exit(f"ERROR: no PDF at {pdf_path}; the xelatex run failed. "
                 f"See {BUILD / 'paper.log'}")
    with fitz.open(pdf_path) as doc:
        n = doc.page_count
    if n == 0:
        sys.exit(f"ERROR: {pdf_path} has 0 pages; the xelatex run failed. "
                 f"See {BUILD / 'paper.log'}")
    with fitz.open(reference) as doc:
        n_ref = doc.page_count
    if n != n_ref:
        print(f"  WARNING: build is {n} pages, committed PDF is {n_ref}. "
              f"Checking the build.")
    print(f"  build validated: {n} pages")


def parse_overfull(log_path: Path) -> list[dict]:
    """Every Overfull box in the log, with an inferred page number.

    Page inference: LaTeX writes "[N" to the log when it starts shipping page N.
    A warning is emitted while breaking the paragraph that lands on the page
    currently being built, so the page in force is the last such marker plus
    one. This is the standard heuristic and it is off by one where a paragraph
    straddles a break, which is why the geometric scan carries the real page.
    """
    text = log_path.read_text(encoding="utf-8", errors="replace")
    page = 1
    out = []
    for line in text.splitlines():
        m = OVERFULL_RE.match(line)
        if m:
            out.append({
                "kind": f"\\{m.group(1)}box",
                "pt": float(m.group(2)),
                "page_est": page,
                "src_lines": (m.group(3), m.group(4)),
            })
        # Count page-open markers. Guard against matching things like "[1]{...}"
        # inside package option echoes by requiring the bracket to start a token.
        for tok in re.findall(r"(?<![\w\]])\[(\d+)", line):
            page = int(tok) + 1
    return out


def geometric_scan(pdf_path: Path) -> list[dict]:
    """Text spans whose right edge crosses the text block, per page."""
    import fitz

    doc = fitz.open(pdf_path)
    hits = []
    for pno in range(doc.page_count):
        worst = None
        for block in doc[pno].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    x1 = span["bbox"][2]
                    if x1 > TEXT_RIGHT_PT + 0.5:
                        if worst is None or x1 > worst["x1"]:
                            worst = {"x1": x1, "text": span["text"]}
        if worst:
            hits.append({
                "page": pno + 1,
                "pt": worst["x1"] - TEXT_RIGHT_PT,
                "off_page": worst["x1"] > PAGE_W_PT,
                "text": worst["text"][:70],
            })
    doc.close()
    return hits


def glyph_check(md_path: Path, pdf_path: Path) -> list[str]:
    """Every literal Greek character in the source must survive into the render.

    Compares source against render rather than against a fixed character list:
    a hardcoded list goes stale the moment the prose changes, and reports
    failures for characters that only ever existed as LaTeX macros.
    """
    import fitz

    md = md_path.read_text(encoding="utf-8")
    # Strip fenced code and inline code: a Greek letter inside a code span is a
    # variable name in a listing, not prose the body font has to render.
    prose = re.sub(r"```.*?```", "", md, flags=re.S)
    prose = re.sub(r"`[^`]*`", "", prose)
    greek = sorted({c for c in prose if "Ͱ" <= c <= "Ͽ"})

    doc = fitz.open(pdf_path)
    rendered = "".join(p.get_text() for p in doc)
    doc.close()

    problems = []
    for ch in greek:
        n_src, n_pdf = prose.count(ch), rendered.count(ch)
        status = "OK" if n_pdf >= 1 else "MISSING"
        print(f"    {ch}  source={n_src:<4d} pdf={n_pdf:<4d} {status}")
        if n_pdf < 1:
            problems.append(f"{ch} (U+{ord(ch):04X}) in source but absent from PDF")
    return problems


def main() -> int:
    build = "--no-build" not in sys.argv
    pdf = OUT_PDF
    failures = []

    if build:
        print("Building with log retention ...")
        log = build_with_log()
        built = BUILD / "paper.pdf"
        assert_usable(built, OUT_PDF)
        pdf = built
        print(f"  log: {log}")
        print(f"  pdf: {pdf}")

        print("\n[1] Overfull boxes from the xelatex log")
        boxes = parse_overfull(log)
        if not boxes:
            print("    none")
        for b in sorted(boxes, key=lambda d: -d["pt"]):
            bad = b["pt"] > FAIL_PT
            src = (f" src lines {b['src_lines'][0]}-{b['src_lines'][1]}"
                   if b["src_lines"][0] else "")
            print(f"    {'FAIL' if bad else 'ok  '} {b['kind']:6s} "
                  f"{b['pt']:7.2f}pt over  ~page {b['page_est']}{src}")
        over = [b for b in boxes if b["pt"] > FAIL_PT]
        if over:
            failures.append(f"{len(over)} overfull box(es) exceed {FAIL_PT}pt "
                            f"(worst {max(b['pt'] for b in over):.2f}pt)")
    else:
        print("Skipping build; checking committed PDF.")

    print("\n[2] Geometric margin scan of the rendered PDF")
    hits = geometric_scan(pdf)
    if not hits:
        print("    none")
    for h in hits:
        bad = h["pt"] > FAIL_PT
        tag = "  OFF PAGE EDGE" if h["off_page"] else ""
        print(f"    {'FAIL' if bad else 'ok  '} page {h['page']:3d}  "
              f"{h['pt']:7.2f}pt past margin{tag}  | {h['text']!r}")
    geo_over = [h for h in hits if h["pt"] > FAIL_PT]
    if geo_over:
        failures.append(f"{len(geo_over)} page(s) with content more than "
                        f"{FAIL_PT}pt past the margin")

    print("\n[3] Greek glyph survival, source vs render")
    problems = glyph_check(SRC_MD, pdf)
    failures.extend(problems)

    print("\n" + "=" * 62)
    if failures:
        print("FAIL")
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
