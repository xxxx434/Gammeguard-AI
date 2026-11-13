"""Crée, signe et vérifie les preuves (SHA-256 + signature Ed25519).

Usage :
    python evidence.py create            # crée une preuve signée pour chaque joueur suspect
    python evidence.py verify P1004      # vérifie la preuve d'un joueur (localement)

La clé du studio est une clé de DÉMO (studio_key.pem), sans rapport avec ta clé Hedera.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

KEY_FILE = "studio_key.pem"
EVIDENCE_DIR = "evidence"
RECORDS_DIR = "records"
THRESHOLD = 70  # score à partir duquel un joueur est signalé


# ---------- clé du studio ----------
def load_or_create_key() -> Ed25519PrivateKey:
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    key = Ed25519PrivateKey.generate()
    with open(KEY_FILE, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
    return key


def pubkey_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()


# ---------- hash et signature ----------
def canonical_bytes(evidence: dict) -> bytes:
    """JSON canonique : mêmes données => mêmes octets => même hash."""
    return json.dumps(
        evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(evidence: dict) -> str:
    return hashlib.sha256(canonical_bytes(evidence)).hexdigest()


def build_record(evidence: dict, key: Ed25519PrivateKey) -> dict:
    """Le 'record' est ce qu'on enverra sur Hedera (petit : < 1 Kio)."""
    digest = sha256_hex(evidence)
    signature = key.sign(bytes.fromhex(digest)).hex()
    return {
        "v": 1,
        "player_id": evidence["player_id"],
        "sha256": digest,
        "signature": signature,
        "studio_pubkey": pubkey_hex(key),
        "created_at": evidence["created_at"],
    }


# ---------- vérification ----------
def verify(evidence: dict, record: dict) -> tuple[bool, str]:
    """Vérifie que la preuve correspond au record (hash) et que le record est signé."""
    digest = sha256_hex(evidence)
    if digest != record["sha256"]:
        return False, "HASH DIFFÉRENT : la preuve a été modifiée"
    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(record["studio_pubkey"]))
        pub.verify(bytes.fromhex(record["signature"]), bytes.fromhex(digest))
    except InvalidSignature:
        return False, "SIGNATURE INVALIDE"
    return True, "OK : preuve identique et signée par le studio"


# ---------- commandes ----------
def cmd_create() -> None:
    with open("players.json", encoding="utf-8") as f:
        players = json.load(f)
    key = load_or_create_key()
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    os.makedirs(RECORDS_DIR, exist_ok=True)

    n = 0
    for p in players:
        if p["suspicion_score"] < THRESHOLD:
            continue
        evidence = {
            "player_id": p["player_id"],
            "suspicion_score": p["suspicion_score"],
            "indicators": p["indicators"],
            "stats": {
                "accuracy": p["accuracy"],
                "reaction_ms": p["reaction_ms"],
                "headshot_ratio": p["headshot_ratio"],
            },
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        record = build_record(evidence, key)
        pid = p["player_id"]
        with open(f"{EVIDENCE_DIR}/{pid}.json", "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, ensure_ascii=False)
        with open(f"{RECORDS_DIR}/{pid}.json", "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        print(f'{pid}  score={p["suspicion_score"]}  sha256={record["sha256"][:16]}...')
        n += 1
    print(f"\n{n} preuves signées -> {EVIDENCE_DIR}/ et {RECORDS_DIR}/")


def cmd_verify(pid: str) -> None:
    with open(f"{EVIDENCE_DIR}/{pid}.json", encoding="utf-8") as f:
        evidence = json.load(f)
    with open(f"{RECORDS_DIR}/{pid}.json", encoding="utf-8") as f:
        record = json.load(f)
    ok, msg = verify(evidence, record)
    print(("✅ " if ok else "❌ ") + msg)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "create":
        cmd_create()
    elif len(sys.argv) >= 3 and sys.argv[1] == "verify":
        cmd_verify(sys.argv[2])
    else:
        print(__doc__)
