# manga2animate-opus-director

Re-evaluation of [Manga2Animate](https://annchenn.github.io/Manga2Animate/) (arXiv 2610.26851) on its MangaEval
benchmark, plus an alternative where a single Claude Opus 5.5 agent directs the whole adaptation.

**Project page:** https://y10ab1.github.io/manga2animate-opus-director/

- `docs/report.md`: setup, results, validity checks and limitations
- `docs/director_brief.md`: the brief given to the Opus director (condition C)
- `results/`: MangaEval scores (`summary.md`, `per_video.csv`, `paper_check.txt`)
- `scripts/eval_all.py`: scoring driver (auto_clip / exact cuts → VBench++ I2VB, SC, BC, MS → DD → DINOv3 I2VS → aesthetic scorers)
- `tools/m2a_tools.py`: logged image, clip, frame and assemble tools used by the director
- `patches/`: Omni backend for the Manga2Animate pipeline (condition B)
- `skills/manga-to-animation/`: Claude skill that runs the whole adaptation as one director agent
- `project_page/`: the GitHub Pages site (`scripts/build_page.py` regenerates `static/`)

Not included: the Manga109-s data, the per-case inputs built from it, and the raw run directories.
Request Manga109-s from [manga109.org](http://www.manga109.org/) and rebuild the cases with `scripts/build_cases.py`.

## License notes
Manga images on the project page are cited from Manga109-s to present research results:
DualJustice © Yusuke Takeyama and LoveHina vol. 01 © Ken Akamatsu. Generated keyframes and videos are derived from these works.
Baseline and Manga2Animate outputs were released by the Manga2Animate authors.
