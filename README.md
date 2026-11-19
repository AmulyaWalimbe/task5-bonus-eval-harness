# Evaluation Harness: Bonus Challenge for Task 5

My Task 5 project tested whether an LLM can reason correctly about a small,
real dataset (2025 Syracuse Women's Lacrosse season stats) by checking its
answers against ground truth I computed myself. My first run was done by hand
in a single chat.

This repository is the bonus challenge. It turns that one-off test into a
repeatable evaluation: a fixed question set, an answer key computed in code,
and an automatic scorer.

Main Task 5 repository (ground truth notebook and original run): (https://github.com/AmulyaWalimbe/Task-04-05---Ground-Truth-to-LLM-Judgment)

## Dataset

**Source:** Syracuse University Athletics, Women's Lacrosse statistics.
Official page: https://cuse.com/sports/womens-lacrosse/stats/2025/

The source does not offer a CSV download, so the tables were manually
transcribed into two CSV files. They are not included here, per the
assignment instructions. Download and transcribe the data from the source
above, or contact me for the exact files, and place them in `data/`:

- `game_log_2025.csv`: 19 rows, one per game
- `player_season_stats_2025.csv`: 32 rows, one per player

**Known data quirk:** the player table sums to 234 total goals, but the team
total row on the same page reports 235. This is a discrepancy in the source
itself, and two of the questions test whether the model notices it.

**Game changer score** (used in the metric questions) = goals + assists +
(2 x game-winning goals).

## What it does
- Asks **19 fixed questions** about the same dataset, in four categories:
  lookup (8), aggregate (7), trap (2, including the 234 vs. 235 goal
  mismatch), and metric (2, using my game changer score).
- Computes every expected answer **from the data in code**, not typed in by
  hand. The answer key matches my ground-truth notebook.
- Requires every answer to end with a line `FINAL ANSWER: <answer>`. A numeric
  answer with no such line is scored wrong, and the scorer never guesses a
  number out of the surrounding text. This separates format failures from
  wrong answers.
- Handles the open-ended **coach question** separately: it cannot be scored by
  string matching, so I grade it by hand against a six-item checklist
  (includes: uses my metric, covers all 5 close losses, notes the data caveat).
- Includes a **self-test** (`--backend mock`) using a perfect and a
  deliberately flawed fake model, to confirm the scorer itself works.

## Files
| File | Purpose |
|---|---|
| `questions.py` | The 19 questions, the answer key (computed from the CSVs), and the coach checklist |
| `scoring.py` | Extracts the `FINAL ANSWER:` line and scores numbers, names, and yes/no |
| `run_eval.py` | Exports prompts, scores answers, writes the results files |
| `responses.csv` | My recorded answers from the run |
| `results/` | Scored output (`scored_*.csv`) and summary (`summary_*.md`) |
| `README.md` | This file |

## How to reproduce
1. Put the two CSV files in `data/` (not included in this repo; see Dataset below).
2. Self-test (no AI needed): `python run_eval.py --backend mock` should report 19/19.
3. Create the prompts: `python run_eval.py --export-prompts` (writes `prompts_to_paste.md`).
4. Paste each prompt into a **new chat** with the model, so earlier answers
   cannot influence later ones. Record each full answer in a spreadsheet with
   columns `model, mode, qid, response`, and save it as `responses.csv`
   (CSV UTF-8).
5. Score it: `python run_eval.py --score-file responses.csv`

No third-party Python packages are needed for these steps (Python 3.9+).

## Method of my run
- **Model:** Claude Sonnet 5.5 (medium), via the Claude chat app
- **Date of run:** November 18, 2026
- **Setup:** 19 prompts, each in a fresh chat, one run per question
- **Scoring:** automatic via `run_eval.py`, coach question graded by hand

## Results
**Overall: 19 of 19 correct (100%).**

| Category | Correct | Total |
|---|---|---|
| lookup | 8 | 8 |
| aggregate | 7 | 7 |
| trap | 2 | 2 |
| metric | 2 | 2 |

- **Questions missed:** None.
- **Format failures vs. wrong answers:** None of either. All 19 responses ended with a `FINAL ANSWER:` line, and every parsed answer matched the answer key, including both trap questions (the 234 vs. 235 goal mismatch).
- **Compared with my original July 29 run:** The headline result is the same: the model got every factual question right both times. What changed is the method. The original was one long chat, graded by hand. This run used 19 fixed questions, each in a fresh chat, scored automatically against an answer key computed in code.

## Limitations
- One model, one run per question, through the chat app. Scores from a single
  run can vary between runs.
- The scorer checks the final answer only, not the reasoning behind it.
- Name matching accepts any answer that contains the expected name.
- A perfect score means this question set is not hard enough to separate this model from a weaker one. A harder set would be needed for that.
- Not covered in this bonus: comparing multiple models, testing larger
  context sizes, and comparing code execution against conversation.

## Repo contents

- `questions.py`, `scoring.py`, `run_eval.py`: the harness code
- `responses.csv`: my recorded answers from the run
- `results/`: scored output and summary from the run
- `README.md`: this file
- `data/`: NOT uploaded (see Dataset above)
