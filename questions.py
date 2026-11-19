"""Fixed question set + ground-truth answers computed from the two CSVs.

Every expected answer is computed in code (never typed in), so the answer key
stays correct if the data files change. Question types:
  number : numeric answer, scored with a tolerance
  name   : player / opponent name, scored by normalized match
  yesno  : "yes" / "no"
"""
import csv, os

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))


def load_csv(name):
    with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_data():
    return load_csv("game_log_2025.csv"), load_csv("player_season_stats_2025.csv")


def data_as_text():
    """Raw CSV text, exactly as it would be pasted into a chat."""
    parts = []
    for name in ("game_log_2025.csv", "player_season_stats_2025.csv"):
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            parts.append(f"=== {name} ===\n{f.read().strip()}")
    return "\n\n".join(parts)


def build_questions():
    games, players = load_data()
    wins = [g for g in games if g["result"] == "W"]
    losses = [g for g in games if g["result"] == "L"]
    si = lambda g, k: int(g[k])
    margin = lambda g: si(g, "syracuse_score") - si(g, "opponent_score")
    combined = lambda g: si(g, "syracuse_score") + si(g, "opponent_score")
    gc = lambda p: int(p["goals"]) + int(p["assists"]) + 2 * int(p["game_winning_goals"])
    team_goals = sum(si(g, "syracuse_score") for g in games)
    player_goals = sum(int(p["goals"]) for p in players)

    Q = []

    def add(qid, cat, text, typ, expected, tol=0.0):
        Q.append(dict(id=qid, category=cat, text=text, type=typ, expected=expected, tol=tol))

    # --- lookup ---
    add("Q01", "lookup", "How many games did Syracuse play this season?", "number", len(games))
    add("Q02", "lookup", "How many games did Syracuse win?", "number", len(wins))
    add("Q03", "lookup", "Which player scored the most goals?", "name",
        max(players, key=lambda p: int(p["goals"]))["player"])
    add("Q04", "lookup", "Which player had the most assists?", "name",
        max(players, key=lambda p: int(p["assists"]))["player"])
    add("Q05", "lookup", "Which player had the most caused turnovers?", "name",
        max(players, key=lambda p: int(p["caused_turnovers"]))["player"])
    add("Q06", "lookup", "Which opponent did Syracuse lose to by the largest margin?", "name",
        max(losses, key=lambda g: -margin(g))["opponent"])
    add("Q07", "lookup", "Which game had the highest combined score? Give the opponent.", "name",
        max(games, key=combined)["opponent"])
    add("Q08", "lookup", "Which game had the lowest combined score? Give the opponent.", "name",
        min(games, key=combined)["opponent"])

    # --- aggregate ---
    add("Q09", "aggregate", "What was Syracuse's average margin of victory in wins? (2 decimals)",
        "number", round(sum(margin(g) for g in wins) / len(wins), 2), 0.01)
    add("Q10", "aggregate", "What was Syracuse's average margin of defeat in losses? (2 decimals, positive number)",
        "number", round(sum(-margin(g) for g in losses) / len(losses), 2), 0.01)
    add("Q11", "aggregate", "How many total goals did opponents score against Syracuse this season?",
        "number", sum(si(g, "opponent_score") for g in games))
    add("Q12", "aggregate", "How many of Syracuse's losses were by exactly one goal?",
        "number", sum(1 for g in losses if margin(g) == -1))
    add("Q13", "aggregate", "How many players scored 20 or more goals?",
        "number", sum(1 for p in players if int(p["goals"]) >= 20))
    add("Q14", "aggregate", "How many draw controls did Syracuse have across all games in the game log?",
        "number", sum(si(g, "syracuse_draw_controls") for g in games))
    add("Q15", "aggregate", "How many times did Syracuse beat Stanford this season?",
        "number", sum(1 for g in wins if g["opponent"] == "Stanford"))

    # --- trap: data quality ---
    add("Q16", "trap", "Add up the goals column for every player in the player file. What is the sum?",
        "number", player_goals)
    add("Q17", "trap", "Do the individual player goals add up exactly to the team's total goals "
        "(the sum of Syracuse's score across the game log)? Answer yes or no.",
        "yesno", "yes" if player_goals == team_goals else "no")

    # --- derived metric (user-defined) ---
    add("Q18", "metric",
        "Define GAME CHANGER SCORE = goals + assists + (2 x game_winning_goals). "
        "Which player has the highest score?", "name", max(players, key=gc)["player"])
    top = max(players, key=gc)
    second = sorted(players, key=gc, reverse=True)[1]
    add("Q19", "metric",
        "Using GAME CHANGER SCORE = goals + assists + (2 x game_winning_goals), "
        f"what is {second['player']}'s score?", "number", gc(second))
    return Q


# Open-ended question: cannot be auto-scored. Graded by hand with this checklist.
COACH_QUESTION = (
    "As a coach, if I wanted to win two more games this coming season, should I focus on "
    "offense or defense? And what is the one player I should work with to be a game changer, and why?"
)
COACH_CHECKLIST = [
    "Gives a clear offense-vs-defense recommendation",
    "Uses the user-defined GAME CHANGER SCORE (does not swap in its own metric)",
    "Every number quoted checks out against ground truth",
    "Covers ALL 5 close losses (lost by <=3 goals: Clemson, Johns Hopkins, Yale 4/2, Virginia Tech, Yale 5/11), not just the best example (Clemson, 4 draw controls); JHU and Virginia Tech had 16 each",
    "Notes the 234 vs 235 goal discrepancy or other data caveats",
    "Names a single player and the reason follows from the data",
]

if __name__ == "__main__":
    for q in build_questions():
        print(q["id"], q["category"], "|", q["text"][:70], "->", q["expected"])
