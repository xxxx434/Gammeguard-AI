"""Envoie les records signés (hash + signature) sur un topic Hedera testnet (HCS).

Usage :  python hedera_submit.py
Lit OPERATOR_ID et OPERATOR_KEY dans le fichier .env.
Option : HEDERA_TLS=0 dans .env si seul le port 50211 passe sur ton réseau.
Crée le topic au premier lancement et garde son ID dans topic_id.txt.
Seul le record (hash, signature, clé publique, date) est publié : aucune donnée de joueur.
"""
import glob
import json
import os
import sys
import time

from email.utils import parsedate_to_datetime

import requests
from dotenv import load_dotenv
from hiero_sdk_python.hapi.services import timestamp_pb2
from hiero_sdk_python.transaction.transaction_id import TransactionId
from hiero_sdk_python import (
    AccountId,
    Client,
    PrivateKey,
    TopicCreateTransaction,
    TopicId,
    TopicMessageSubmitTransaction,
)

TOPIC_FILE = "topic_id.txt"
RECORDS_DIR = "records"
SUBMITTED_FILE = "submitted.json"  # évite de renvoyer deux fois la même preuve
ATTEMPTS = 5
MIRROR_URL = "https://testnet.mirrornode.hedera.com/api/v1/network/nodes?limit=1"


def get_client():
    """Chaque nouveau Client tire un nœud au hasard : réessayer change de nœud."""
    load_dotenv()
    op_id, op_key = os.getenv("OPERATOR_ID"), os.getenv("OPERATOR_KEY")
    if not op_id or not op_key:
        sys.exit("OPERATOR_ID / OPERATOR_KEY introuvables dans .env")
    operator_id = AccountId.from_string(op_id.strip())
    operator_key = PrivateKey.from_string_der(op_key.strip())
    client = Client()  # testnet par défaut
    if os.getenv("HEDERA_TLS", "1").strip() == "0":
        client.set_transport_security(False)  # port 50211 au lieu de 50212
    client.set_operator(operator_id, operator_key)

    # Hedera refuse une transaction si l'heure du PC diffère de la sienne (INVALID_TRANSACTION_START).
    # On mesure l'écart et on le compense dans l'heure de départ de chaque transaction.
    offset = clock_offset()
    if abs(offset) > 2:
        print(f"  Horloge du PC décalée de {offset:+.0f} s par rapport à Hedera : correction automatique.")

    def corrected_transaction_id():
        t = time.time() - offset - 10  # 10 s de marge ; la transaction reste valide 120 s
        sec = int(t)
        return TransactionId(operator_id, timestamp_pb2.Timestamp(seconds=sec, nanos=int((t - sec) * 1e9)))

    client.generate_transaction_id = corrected_transaction_id
    return client, operator_key


def clock_offset() -> float:
    """Écart (heure du PC - heure du serveur) en secondes, via l'en-tête HTTP Date (précision ~1 s)."""
    try:
        t0 = time.time()
        r = requests.get(MIRROR_URL, timeout=10)
        t1 = time.time()
        server = parsedate_to_datetime(r.headers["Date"]).timestamp() + 0.5
        return (t0 + t1) / 2 - server
    except Exception:  # noqa: BLE001
        return 0.0  # mesure impossible : on garde le comportement par défaut du SDK


def retry(action_name, fn):
    """Exécute fn(client, key) avec un nouveau client à chaque tentative."""
    last = None
    for attempt in range(1, ATTEMPTS + 1):
        client = None
        try:
            client, key = get_client()
            result = fn(client, key)
            client.close()
            return result
        except (OSError, ConnectionError, ValueError) as e:  # TimeoutError est un OSError
            if isinstance(e, ValueError) and "certificate" not in str(e).lower():
                raise  # vraie erreur (clé invalide, etc.) : on ne réessaie pas
            last = e
            print(f"  {action_name} : tentative {attempt}/{ATTEMPTS} échouée ({type(e).__name__}), autre nœud...")
            try:
                if client:
                    client.close()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
        except Exception as e:  # noqa: BLE001
            if "INVALID_TRANSACTION_START" in str(e):
                sys.exit(
                    "\nL'horloge de ton PC est décalée par rapport à Hedera (INVALID_TRANSACTION_START).\n"
                    "Synchronise l'heure de Windows (Paramètres > Heure et langue > Date et heure >\n"
                    "'Synchroniser maintenant'), vérifie le fuseau horaire, puis relance.\n"
                    "Pour mesurer l'écart : python check_network.py"
                )
            raise
    sys.exit(
        f"\nImpossible de joindre Hedera après {ATTEMPTS} essais ({type(last).__name__}).\n"
        "Lance : python check_network.py  pour savoir si ton réseau bloque Hedera."
    )


def create_topic(client, operator_key):
    tx = (
        TopicCreateTransaction(
            memo="Anti-cheat evidence (demo)", admin_key=operator_key.public_key()
        )
        .freeze_with(client)
        .sign(operator_key)
    )
    receipt = tx.execute(client)
    return str(receipt.topic_id)


def submit_message(topic_id, message):
    def _do(client, operator_key):
        tx = (
            TopicMessageSubmitTransaction()
            .set_topic_id(TopicId.from_string(topic_id))
            .set_message(message)
            .freeze_with(client)
            .sign(operator_key)
        )
        tx.execute(client)

    retry("envoi", _do)


def main():
    if os.path.exists(TOPIC_FILE):
        topic_id = open(TOPIC_FILE, encoding="utf-8").read().strip()
        print(f"Topic existant : {topic_id}")
    else:
        topic_id = retry("création du topic", create_topic)
        with open(TOPIC_FILE, "w", encoding="utf-8") as f:
            f.write(topic_id)
        print(f"Topic créé : {topic_id}")

    submitted = {}
    if os.path.exists(SUBMITTED_FILE):
        submitted = json.load(open(SUBMITTED_FILE, encoding="utf-8"))

    files = sorted(glob.glob(f"{RECORDS_DIR}/*.json"))
    if not files:
        sys.exit("Aucun record. Lance d'abord : python evidence.py create")

    for path in files:
        record = json.load(open(path, encoding="utf-8"))
        pid = record["player_id"]
        if submitted.get(pid) == record["sha256"]:
            print(f"{pid} : déjà envoyé, on saute")
            continue
        message = json.dumps(record, separators=(",", ":"))
        assert len(message.encode()) < 1024, "message trop long pour HCS (1 Kio)"
        submit_message(topic_id, message)
        submitted[pid] = record["sha256"]
        json.dump(submitted, open(SUBMITTED_FILE, "w", encoding="utf-8"), indent=2)
        print(f"{pid} : envoyé sur Hedera (sha256 {record['sha256'][:16]}...)")

    print(f"\nTerminé. Vois le topic sur : https://hashscan.io/testnet/topic/{topic_id}")


if __name__ == "__main__":
    main()
