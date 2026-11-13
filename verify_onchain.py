"""Vérifie une preuve en se basant UNIQUEMENT sur ce qui est publié sur Hedera.

Usage :  python verify_onchain.py P1009
         python verify_onchain.py P1009 chemin/vers/autre_fichier.json

Étapes : lire les messages du topic via le nœud miroir public, retrouver le record
du joueur, recalculer le hash du fichier de preuve, comparer, vérifier la signature.
On ne fait donc PAS confiance au dossier records/ du studio, seulement à la chaîne.
"""
import base64
import json
import sys

import requests

from evidence import verify

MIRROR = "https://testnet.mirrornode.hedera.com/api/v1"


def fetch_records(topic_id: str):
    """Retourne la liste des (record, consensus_timestamp, sequence_number) du topic."""
    url = f"{MIRROR}/topics/{topic_id}/messages?limit=100&order=asc"
    out = []
    while url:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        for m in data.get("messages", []):
            try:
                record = json.loads(base64.b64decode(m["message"]).decode("utf-8"))
            except (ValueError, KeyError):
                continue  # message qui n'est pas de notre format : on ignore
            out.append((record, m["consensus_timestamp"], m["sequence_number"]))
        nxt = data.get("links", {}).get("next")
        url = ("https://testnet.mirrornode.hedera.com" + nxt) if nxt else None
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pid = sys.argv[1]
    evidence_path = sys.argv[2] if len(sys.argv) > 2 else f"evidence/{pid}.json"
    topic_id = open("topic_id.txt", encoding="utf-8").read().strip()

    with open(evidence_path, encoding="utf-8") as f:
        evidence = json.load(f)

    matches = [x for x in fetch_records(topic_id) if x[0].get("player_id") == pid]
    if not matches:
        sys.exit(f"Aucun record pour {pid} sur le topic {topic_id} (attends quelques secondes ?)")

    record, ts, seq = matches[-1]  # le plus récent
    ok, msg = verify(evidence, record)
    print(f"Topic {topic_id} · message #{seq} · horodatage consensus {ts}")
    print(("✅ " if ok else "❌ ") + msg)


if __name__ == "__main__":
    main()
