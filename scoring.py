import re, unicodedata

FINAL_RE = re.compile(r"FINAL ANSWER\s*:\s*(.+)", re.IGNORECASE)


def extract_final(response: str):
    """Return (final_answer_text, found_marker). Uses the LAST 'FINAL ANSWER:' line."""
    m = FINAL_RE.findall(response or "")
    if m:
        return m[-1].strip().strip("*`_ "), True
    return (response or "").strip(), False


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()


def _numbers(s):
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", s)]


def score(question, response):
    """Return dict(correct: bool, parsed: str, found_marker: bool, note: str)."""
    final, found = extract_final(response)
    typ, exp = question["type"], question["expected"]
    if typ == "number":
        if not found:
            return dict(correct=False, parsed=final[:60], found_marker=False,
                        note="no FINAL ANSWER line; numbers not guessed from prose")
        nums = _numbers(final)
        ok = len(nums) >= 1 and abs(nums[0] - float(exp)) <= question["tol"] + 1e-9
        return dict(correct=ok, parsed=str(nums[0]) if nums else final[:60],
                    found_marker=True, note="")
    if typ == "name":
        toks = _norm(final)
        exp_toks = _norm(exp)
        ok = all(t in toks for t in exp_toks)
        return dict(correct=ok, parsed=final[:60], found_marker=found, note="")
    if typ == "yesno":
        w = _norm(final)
        got = "yes" if (w and w[0] == "yes") else "no" if (w and w[0] == "no") else "?"
        return dict(correct=(got == exp), parsed=got, found_marker=found, note="")
    raise ValueError(typ)
