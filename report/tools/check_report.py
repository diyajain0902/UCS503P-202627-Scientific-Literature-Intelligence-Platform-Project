"""Static checks for the LaTeX report (no TeX installation needed).

Catches the errors that most often break an Overleaf compile:
missing \\input files, undefined \\ref/\\autoref labels, unknown \\cite keys, unbalanced braces or
environments, non-ASCII characters, and unescaped _ or # outside math, listings and comments.
It is not a LaTeX parser: a clean result does not prove that the document compiles.

Usage (from the repository root):  python report/tools/check_report.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERBATIM_ENVS = ("lstlisting",)


def strip_comments(line: str) -> str:
    out, i = [], 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            out.append(line[i : i + 2])
            i += 2
            continue
        if ch == "%":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def load(path: Path) -> list[tuple[int, str]]:
    """Lines with comments removed and verbatim environments blanked."""
    lines, in_verb = [], False
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if in_verb:
            if re.search(r"\\end\{(%s)\}" % "|".join(VERBATIM_ENVS), raw):
                in_verb = False
                lines.append((no, raw[raw.index("\\end") :]))
            else:
                lines.append((no, ""))
            continue
        line = strip_comments(raw)
        if re.search(r"\\begin\{(%s)\}" % "|".join(VERBATIM_ENVS), line):
            in_verb = True
            # keep the options line (it may carry a \label) but not the listing body
            lines.append((no, line))
            continue
        lines.append((no, line))
    return lines


def main() -> int:
    problems: list[str] = []
    main_tex = ROOT / "main.tex"
    files = [main_tex]
    seen: set[Path] = set()
    labels: dict[str, str] = {}
    refs: list[tuple[str, str]] = []
    cites: list[tuple[str, str]] = []

    while files:
        path = files.pop(0)
        if path in seen:
            continue
        seen.add(path)
        rel = path.relative_to(ROOT).as_posix()
        text_lines = load(path)
        depth, env_stack, in_math_env = 0, [], False
        raw_text = path.read_text(encoding="utf-8")
        for no, ch in ((n, c) for n, line in enumerate(raw_text.splitlines(), 1) for c in line):
            if ord(ch) > 127:
                problems.append(f"{rel}:{no}: non-ASCII character {ch!r}")
        for no, line in text_lines:
            where = f"{rel}:{no}"
            for target in re.findall(r"\\(?:input|include|fitfigure)\{([^}#]+)\}", line):
                candidate = ROOT / (target if target.endswith(".tex") else target + ".tex")
                if candidate.exists():
                    files.append(candidate)
                else:
                    problems.append(f"{where}: missing input file {target}")
            option_labels = re.findall(r"\blabel=([^,\]\s]+)", line) if "\\begin{lstlisting}" in line else []
            for name in re.findall(r"\\label\{([^}]+)\}", line) + option_labels:
                if name in labels:
                    problems.append(f"{where}: duplicate label {name} (also {labels[name]})")
                labels[name] = where
            for name in re.findall(r"\\(?:auto|page)?ref\{([^}]+)\}", line):
                refs.append((name, where))
            for group in re.findall(r"\\(?:text|paren)?cite\{([^}]+)\}", line):
                cites.extend((k.strip(), where) for k in group.split(","))
            unescaped = re.sub(r"\\[{}]", "", line)
            for ch in unescaped:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth < 0:
                        problems.append(f"{where}: unmatched closing brace")
                        depth = 0
            for kind, env in re.findall(r"\\(begin|end)\{([^}]+)\}", line):
                if kind == "begin":
                    env_stack.append((env, where))
                elif not env_stack or env_stack[-1][0] != env:
                    problems.append(f"{where}: \\end{{{env}}} does not match the open environment")
                else:
                    env_stack.pop()
            if re.search(r"\\begin\{(equation|align)\*?\}", line):
                in_math_env = True
            if in_math_env:
                if re.search(r"\\end\{(equation|align)\*?\}", line):
                    in_math_env = False
                continue
            no_math = re.sub(r"\$[^$]*\$", "", line)
            no_cmds = re.sub(r"\\(label|ref|autoref|cite|input|include|url|href|addbibresource)\{[^}]*\}", "", no_math)
            if re.search(r"(?<!\\)_", no_cmds):
                problems.append(f"{where}: unescaped _ outside math")
            if re.search(r"(?<!\\)#(?!\d)", no_cmds) and "\\newcommand" not in no_cmds and "/.style" not in no_cmds \
                    and "\\fitfigure" not in no_cmds and ".pic" not in no_cmds:
                problems.append(f"{where}: unescaped # outside a macro definition")
        if depth != 0:
            problems.append(f"{rel}: brace depth {depth} at end of file")
        for env, where in env_stack:
            problems.append(f"{where}: \\begin{{{env}}} never closed")

    for name, where in refs:
        if name not in labels:
            problems.append(f"{where}: undefined reference {name}")
    bib = (ROOT / "references.bib").read_text(encoding="utf-8")
    keys = re.findall(r"@\w+\{([^,]+),", bib)
    for key in {k for k in keys if keys.count(k) > 1}:
        problems.append(f"references.bib: duplicate key {key}")
    if bib.count("{") != bib.count("}"):
        problems.append("references.bib: unbalanced braces")
    for key, where in cites:
        if key not in keys:
            problems.append(f"{where}: unknown citation key {key}")
    unused = sorted(set(keys) - {k for k, _ in cites})

    print(f"files checked: {len(seen)}; labels: {len(labels)}; references: {len(refs)}; "
          f"citations: {len(cites)} ({len({k for k, _ in cites})} keys); bib entries: {len(keys)}")
    if unused:
        print("bib entries never cited (not printed by biblatex): " + ", ".join(unused))
    for problem in problems:
        print("PROBLEM", problem)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
