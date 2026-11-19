"""Evaluation harness: ask fixed questions, score against ground truth.

Usage
  python run_eval.py --backend mock                      # self-test, no API needed
  python run_eval.py --backend anthropic --model <id>    # needs ANTHROPIC_API_KEY
  python run_eval.py --export-prompts                    # writes prompts_to_paste.md
  python run_eval.py --score-file my_responses.csv       # score answers pasted from ChatGPT/Copilot/etc.
  python run_eval.py --score-xlsx evaluation_answers.xlsx        # score the filled-in spreadsheet
  python run_eval.py --score-docx evaluation_answer_sheet.docx   # score the filled-in Word answer sheet

responses.csv columns: model,mode,qid,response (optional: run)
"""
import argparse, csv, json, os, sys, time, urllib.request, collections
from questions import build_questions, data_as_text, COACH_QUESTION, COACH_CHECKLIST
from scoring import score

OUT = os.path.join(os.path.dirname(__file__), "results")

INSTRUCTIONS = (
    "You are given two CSV files about the 2025 Syracuse women's lacrosse season. "
    "Answer the question using only this data. Think step by step if you need to, "
    "then end your reply with one line in exactly this form:\nFINAL ANSWER: <answer>\n"
    "(a number, a name, or yes/no only)."
)


def build_prompt(q, data_text):
    return f"{INSTRUCTIONS}\n\n{data_text}\n\nQUESTION: {q['text']}"


# ---------------- backends ----------------
def ask_anthropic(prompt, model):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("Set ANTHROPIC_API_KEY first (or use --export-prompts for manual runs).")
    body = json.dumps({"model": model, "max_tokens": 1500,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    return "".join(b.get("text", "") for b in d["content"])


def ask_mock(prompt, q, quirk):
    """Deterministic fake model for testing the harness itself."""
    exp = q["expected"]
    if quirk == "perfect":
        return f"Working it out...\nFINAL ANSWER: {exp}"
    if quirk == "sloppy":  # wrong on trap/metric questions, no marker on Q01
        if q["category"] in ("trap", "metric"):
            wrong = {"number": float(exp) + 1 if q["type"] == "number" else exp,
                     "name": "Somebody Else", "yesno": "yes"}[q["type"]]
            return f"FINAL ANSWER: {wrong}"
        if q["id"] == "Q01":
            return f"I think they played {exp} games."
        return f"FINAL ANSWER: {exp}"
    raise ValueError(quirk)


# ---------------- core ----------------
def run(backend, model, mode="chat", quirk="perfect", repeats=1):
    qs, rows = build_questions(), []
    data_text = data_as_text()
    for rep in range(1, repeats + 1):
        for q in qs:
            prompt = build_prompt(q, data_text)
            t0 = time.time()
            resp = ask_anthropic(prompt, model) if backend == "anthropic" else ask_mock(prompt, q, quirk)
            rows.append(dict(model=model, mode=mode, run=rep, qid=q["id"], response=resp,
                             seconds=round(time.time() - t0, 2)))
            print(f"run {rep} {q['id']} done", flush=True)
    return rows


def score_rows(rows):
    qmap = {q["id"]: q for q in build_questions()}
    out = []
    for r in rows:
        q = qmap[r["qid"]]
        s = score(q, r["response"])
        out.append(dict(model=r["model"], mode=r["mode"], run=r.get("run") or 1, qid=q["id"], category=q["category"],
                        question=q["text"], expected=q["expected"], parsed=s["parsed"],
                        correct=int(s["correct"]), found_marker=int(s["found_marker"]),
                        note=s["note"], response=r["response"]))
    return out


def summarize(scored):
    lines = ["# Evaluation summary\n"]
    groups = collections.defaultdict(list)
    for r in scored:
        groups[(r["model"], r["mode"])].append(r)
    for (m, mode), rs in groups.items():
        n, c = len(rs), sum(r["correct"] for r in rs)
        runs = len({r["run"] for r in rs})
        lines.append(f"## {m} ({mode}): {c}/{n} correct ({100*c/n:.0f}%) over {runs} run(s)\n")
        lines.append("| category | correct | total |\n|---|---|---|")
        cats = collections.defaultdict(lambda: [0, 0])
        for r in rs:
            cats[r["category"]][0] += r["correct"]; cats[r["category"]][1] += 1
        for k, (a, b) in cats.items():
            lines.append(f"| {k} | {a} | {b} |")
        misses = [r for r in rs if not r["correct"]]
        if misses:
            lines.append("\nMissed:\n")
            for r in misses:
                lines.append(f"- run {r['run']} {r['qid']} expected `{r['expected']}`, got `{r['parsed']}` {r['note']}")
        lines.append("")
    return "\n".join(lines)


def save(scored):
    os.makedirs(OUT, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUT, f"scored_{stamp}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scored[0].keys()))
        w.writeheader(); w.writerows(scored)
    summ = summarize(scored)
    with open(os.path.join(OUT, f"summary_{stamp}.md"), "w", encoding="utf-8") as f:
        f.write(summ)
    print(summ); print(f"Saved to {path}")


def read_docx_answers(path):
    """Read answers from evaluation_answer_sheet.docx (needs: pip install python-docx)."""
    try:
        import docx
    except ImportError:
        sys.exit("Run this once first:  pip install python-docx")
    import re
    d = docx.Document(path)
    model, cur, collecting, buf, rows = "", None, False, [], []

    def flush():
        if cur and cur != "COACH":
            text = "\n".join(buf).strip()
            if text:
                rows.append(dict(model=model, mode="chat", run=1, qid=cur, response=text))
    for para in d.paragraphs:
        t = para.text.strip()
        if t.upper().startswith("MODEL NAME:"):
            model = t.split(":", 1)[1].strip()
        elif para.style.name.lower().startswith("heading 2") and re.match(r"(Q\d{2}|COACH) - ", t):
            flush(); buf, collecting = [], False
            cur = re.match(r"(Q\d{2}|COACH)", t).group(1)
        elif t.startswith("PROMPT (triple-click"):
            collecting = False
        elif t.startswith("ANSWER - paste"):
            collecting = True
        elif collecting:
            buf.append(para.text)
    flush()
    if not model:
        sys.exit("Type the model name after 'MODEL NAME:' in the document first.")
    print(f"Read {len(rows)} answers for model '{model}'")
    return rows


def read_xlsx_answers(path):
    """Read answers from evaluation_answers.xlsx (needs: pip install openpyxl)."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit("Run this once first:  pip install openpyxl")
    import re
    ws = load_workbook(path, data_only=True).active
    model = str(ws["B1"].value or "").strip()
    if not model:
        sys.exit("Type the model name in the yellow cell B1 first.")
    rows = []
    for r in range(1, ws.max_row + 1):
        qid, ans = ws.cell(r, 1).value, ws.cell(r, 2).value
        if qid and re.fullmatch(r"Q\d{2}", str(qid).strip()) and ans and str(ans).strip():
            rows.append(dict(model=model, mode="chat", run=1, qid=str(qid).strip(), response=str(ans).strip()))
    print(f"Read {len(rows)} answers for model '{model}'")
    return rows


def export_prompts():
    data_text = data_as_text()
    with open("prompts_to_paste.md", "w", encoding="utf-8") as f:
        f.write("# Paste each prompt into a NEW chat (fresh context). Save answers to responses.csv "
                "with columns: model,mode,qid,response\n\n")
        for q in build_questions():
            f.write(f"## {q['id']}\n\n```\n{build_prompt(q, data_text)}\n```\n\n")
        f.write(f"## COACH (hand-graded)\n\n{COACH_QUESTION}\n\nChecklist:\n")
        for c in COACH_CHECKLIST:
            f.write(f"- [ ] {c}\n")
    print("Wrote prompts_to_paste.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["mock", "anthropic"])
    ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--mode", default="chat")
    ap.add_argument("--quirk", default="perfect")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--export-prompts", action="store_true")
    ap.add_argument("--score-file")
    ap.add_argument("--score-docx")
    ap.add_argument("--score-xlsx")
    a = ap.parse_args()
    if a.export_prompts:
        export_prompts()
    elif a.score_xlsx:
        save(score_rows(read_xlsx_answers(a.score_xlsx)))
    elif a.score_docx:
        save(score_rows(read_docx_answers(a.score_docx)))
    elif a.score_file:
        with open(a.score_file, newline="", encoding="utf-8-sig") as f:
            save(score_rows(list(csv.DictReader(f))))
    elif a.backend:
        save(score_rows(run(a.backend, a.model if a.backend == "anthropic" else f"mock-{a.quirk}",
                            a.mode, a.quirk, a.repeats)))
    else:
        ap.print_help()
