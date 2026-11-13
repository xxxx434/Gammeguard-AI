"""Génère des joueurs simulés et calcule un score de suspicion (règles simples).

Aucune donnée réelle : tout est simulé. Sortie : players.json
"""
import json
import random

random.seed(42)  # résultats reproductibles pour la démo

N_NORMAL = 8
N_CHEATERS = 3


def make_player(pid: int, cheater: bool) -> dict:
    if cheater:
        accuracy = round(random.uniform(0.85, 0.99), 2)        # précision de tir
        reaction_ms = random.randint(60, 110)                   # temps de réaction
        headshot_ratio = round(random.uniform(0.70, 0.95), 2)   # part de tirs à la tête
    else:
        accuracy = round(random.uniform(0.20, 0.55), 2)
        reaction_ms = random.randint(180, 320)
        headshot_ratio = round(random.uniform(0.05, 0.30), 2)
    return {
        "player_id": f"P{pid:04d}",
        "accuracy": accuracy,
        "reaction_ms": reaction_ms,
        "headshot_ratio": headshot_ratio,
    }


def suspicion(p: dict) -> tuple[int, list[str]]:
    """Retourne (score 0-100, indicateurs détectés). Règles volontairement simples."""
    score, flags = 0, []
    if p["accuracy"] > 0.80:
        score += 35
        flags.append("précision anormalement élevée")
    if p["reaction_ms"] < 120:
        score += 35
        flags.append("temps de réaction quasi impossible")
    if p["headshot_ratio"] > 0.60:
        score += 30
        flags.append("taux de tirs à la tête anormal")
    return score, flags


def main() -> None:
    players = []
    pid = 1000
    for cheater in [False] * N_NORMAL + [True] * N_CHEATERS:
        pid += 1
        p = make_player(pid, cheater)
        p["suspicion_score"], p["indicators"] = suspicion(p)
        players.append(p)
    random.shuffle(players)

    with open("players.json", "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

    print(f"{len(players)} joueurs simulés -> players.json\n")
    for p in players:
        mark = "SUSPECT" if p["suspicion_score"] >= 70 else "ok"
        print(f'{p["player_id"]}  score={p["suspicion_score"]:3d}  {mark}')


if __name__ == "__main__":
    main()
