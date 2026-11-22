"""Regenerate paper/pairs_stat_arb.pdf from paper/pairs_stat_arb.md via pandoc + xelatex.

The PDF is a build artifact of the markdown - any divergence is a bug. To
keep that promise honest, this script renders only through xelatex. If
xelatex fails for any reason (pandoc absent, TinyTeX missing, font missing,
TeX error), the script exits non-zero and leaves the existing PDF on disk
untouched, rather than substituting a different engine that produces a
visually plausible but wrong-pipeline artifact.

Usage:
    python scripts/render_paper.py

Output:
    paper/pairs_stat_arb.pdf (atomic replace on xelatex success only)

Prerequisites (see Appendix A of the paper):
    pandoc, TinyTeX (xelatex), and three CTAN packages installed once via
    `tlmgr install tex-gyre booktabs fancyhdr`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_MD = ROOT / "paper" / "pairs_stat_arb.md"
OUT_PDF = ROOT / "paper" / "pairs_stat_arb.pdf"
FIGURES = ROOT / "figures"


def pandoc_cmd(out_path: Path) -> list[str]:
    return [
        "pandoc",
        str(SRC_MD),
        "-o", str(out_path),
        "--pdf-engine=xelatex",
        "--citeproc",
        "--resource-path", f"{ROOT}{':' if sys.platform != 'win32' else ';'}{FIGURES}",
        "-V", "geometry:margin=1in",
        "-V", "fontsize=11pt",
        "-V", "papersize=letter",
        "-V", "linkcolor=black",
        "-V", "urlcolor=black",
        # Body + mono fonts with Greek coverage (α, β, μ, σ, ε appear throughout
        # the prose). From the tex-gyre CTAN collection - install once via
        # `tlmgr install tex-gyre`. CTAN-distributed rather than OS-bundled, so
        # the render reproduces on any TinyTeX install after that one command.
        "-V", "mainfont=TeX Gyre Pagella",
        "-V", "monofont=TeX Gyre Cursor",
        # Suppress \parskip inside pandoc's Shaded (highlighted-code) wrapper so
        # consecutive verbatim lines pack at the natural baseline instead of
        # picking up the body-paragraph skip. Scoped to Shaded; body leading
        # untouched.
        "-V", r"header-includes=\AtBeginEnvironment{Shaded}{\setlength{\parskip}{0pt}}",
        # booktabs for the explicit-LaTeX data tables (4.1, 4.2, 4.3, 4.7) -
        # gives \toprule/\midrule/\bottomrule. Pandoc may load it already for
        # its own markdown tables; \usepackage is idempotent.
        "-V", r"header-includes=\usepackage{booktabs}",
        # Short-title running heads and a centered folio - standard working-paper
        # furniture. fancyhdr must clear the default header rule on plain pages
        # (chapter/section openers) or the first page picks up an inconsistent rule.
        "-V", (r"header-includes=\usepackage{fancyhdr}\pagestyle{fancy}"
               r"\fancyhf{}\renewcommand{\headrulewidth}{0pt}"
               r"\fancyhead[L]{\footnotesize Brandes}"
               r"\fancyhead[R]{\footnotesize A cointegration gate is useful but not sufficient}"
               r"\fancyfoot[C]{\thepage}"),
    ]


def main() -> int:
    print(f"Source : {SRC_MD}")
    print(f"Output : {OUT_PDF}")

    if shutil.which("pandoc") is None:
        print("  ERROR: pandoc not found on PATH. Install pandoc and retry.", file=sys.stderr)
        return 1

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    # Render to a sibling temp path; replace the canonical PDF only on a clean
    # exit. A mid-render failure cannot leave a partial or wrong-pipeline file
    # masquerading as the committed artifact.
    tmp_path = OUT_PDF.with_suffix(".tmp.pdf")
    try:
        subprocess.run(pandoc_cmd(tmp_path), check=True, cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        tmp_path.unlink(missing_ok=True)
        print(
            f"  ERROR: pandoc+xelatex render failed (exit {exc.returncode}). "
            f"Canonical PDF left untouched.",
            file=sys.stderr,
        )
        return 1

    tmp_path.replace(OUT_PDF)
    print("  rendered via pandoc + xelatex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
