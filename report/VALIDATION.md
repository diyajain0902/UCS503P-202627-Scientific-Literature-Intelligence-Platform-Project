# Report Validation Summary (2026-10-09)

## Compilation

**Not compiled.** The machine used to write the report has no TeX distribution, Biber, Java or PlantUML, and the
team chose to compile on Overleaf instead of downloading a toolchain. **No PDF was generated and no page was visually
inspected.** The first Overleaf compile is the first real compilation; see the checklist below.

## Static checks that were run

`python report/tools/check_report.py`, last result:

```
files checked: 25; labels: 44; references: 49; citations: 58 (32 keys); bib entries: 32
OK
```

The checks cover every `\input` and `\fitfigure` file (all present), every `\ref`/`\autoref` (all labels defined),
every `\cite` (all keys present, no unused or duplicate entries), brace and environment balance per file, ASCII-only
source, and unescaped `_` and `#` outside math, listings and macro definitions. **This is not a LaTeX parser.** It
cannot detect TikZ errors, overfull boxes, float placement or wrong package options.

## Template

- `tietreport.cls` v1.0.4 was read from the official source repository (github.com/bvraghav/tietreport, `develop`
  branch, MIT). The title-page commands used (`\TitlePageHeader`, `\ProjectTitle`, `\ProjectSubTitle`, `\author`,
  `\TitlePageSubText`, `\AdvisorName`, `\TitlePageFooterText`, `\maketitle`) are the ones the class defines.
- The shared Overleaf project itself was not opened (it requires a browser session); the class file from the source
  repository was used instead.

## References

Every bibliography entry was verified on 2026-10-09:

- DOI entries against Crossref (titles, authors, venues, pages).
- arXiv entries against arXiv abstract pages or the arXiv API metadata stored in the project's evaluation database.
- URLs: all returned HTTP 200.

For the BM25 monograph, Crossref's volume and page data differ from the commonly cited ones, so those fields were
omitted and the DOI is given.

## Factual consistency

Implementation claims were checked against the source files named in each chapter and in the diagram headers.
Every number was taken from `eval/runs/` records, the release and audit documents in `docs/`, or commands run during
the project. Corrections made while writing:

- ADR alternatives table re-read from the ADRs.
- Python-version rationale taken from ADR-0004.
- Chunk-identifier derivation taken from `chunking.py`.

Placeholders and limitations are stated, not filled in.

## Checklist for the first Overleaf compile

- [ ] Compiler pdfLaTeX; the log has no errors; Biber ran (no `[?]` citations).
- [ ] Title page: placeholders replaced; layout as in the TIET template.
- [ ] Table of contents, list of figures, list of tables populated.
- [ ] Figures 4.1–4.2 and the five UML figures in Chapter 5 render without clipping. The services class diagram and
      the sequence diagram are on landscape pages.
- [ ] No overfull boxes worth fixing (check the log for `Overfull \hbox`).
- [ ] Bibliography printed with all entries.

Report any compile error back with the log line, and it will be fixed in the TikZ or LaTeX source.
