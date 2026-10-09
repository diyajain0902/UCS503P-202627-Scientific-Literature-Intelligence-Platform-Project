# Project Report (LaTeX, TIET report class)

UCS503P project report for the Scientific Literature Intelligence Platform, written with the `tietreport` class
(v1.0.4, MIT licence, by R. B. Venkataramaiyer; vendored here as `tietreport.cls` with `tietreport-LICENSE.txt` so
the project compiles without depending on the TeX distribution's version).

## Build on Overleaf (the intended route)

1. Zip the `report/` folder and upload it to Overleaf (*New Project → Upload Project*), or upload the files into
   a copy of the supplied TIET template project. Keep the folder structure.
2. *Menu → Settings*: **Compiler: pdfLaTeX**, **Main document: `main.tex`**. Overleaf runs Biber automatically for
   biblatex documents.
3. Recompile. If references show as `[?]`, recompile once more (pdfLaTeX → Biber → pdfLaTeX → pdfLaTeX).

## Build locally

Requires a TeX distribution with pdfLaTeX, Biber and the packages listed at the top of `main.tex`
(TikZ, biblatex, listings, rotating, longtable, tabularx, booktabs, microtype, lmodern, csquotes).

```bash
cd report
latexmk -pdf main.tex
```

Or by hand: `pdflatex main`, `biber main`, `pdflatex main`, `pdflatex main`.

## Before submitting

- Replace the title-page placeholders in `main.tex`: `[GROUP NUMBER]`, `[YEAR]`, `[EVALUATION STAGE]`.
- Add a certificate or student declaration page only if the department requires one (see the comment in
  `main.tex`); none is included, so that nothing is signed or approved on anyone's behalf.
- Run the static checks: `python report/tools/check_report.py` from the repository root.

## Layout

| Path | Contents |
|------|----------|
| `main.tex` | Entry point: preamble, title page, front matter, chapter and appendix order |
| `frontmatter/` | Abstract, abbreviations |
| `chapters/01-…10-*.tex` | Chapters 1–10 |
| `appendices/` | Setup, API and configuration, traceability matrix, run records |
| `figures/uml/*.tex` | **Editable UML sources** (TikZ): use case, class (domain, services), sequence, activity, communication |
| `figures/arch/*.tex` | Deployment and data-flow diagrams (TikZ) |
| `references.bib` | Bibliography (biblatex, Biber); every entry checked on 2026-10-09 |
| `tools/check_report.py` | Static checks (inputs, labels, citations, braces, environments, ASCII, escaping) |
| `VALIDATION.md` | What was and was not verified |

The UML diagrams are TikZ code compiled with the report, so the editable source and the rendered figure are the
same file. PlantUML was not used because no Java runtime or PlantUML installation was available and the team chose
the Overleaf-only route.
