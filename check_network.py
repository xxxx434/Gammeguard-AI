"""Teste si ton réseau laisse passer les connexions vers Hedera testnet.

Usage :  python check_network.py
Aucune bibliothèque externe, aucune clé : tu peux le lancer sans risque.
"""
import socket
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

HOSTS = [f"{i}.testnet.hedera.com" for i in range(4)]
PORTS = {50211: "sans TLS", 50212: "avec TLS (utilisé par défaut par le SDK)"}


def tcp_ok(host: str, port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def clock_report(server_date: str | None) -> str:
    """Compare l'horloge du PC à celle du serveur (en-tête HTTP Date, précision ~1 s).

    Hedera refuse les transactions (INVALID_TRANSACTION_START) si l'écart dépasse
    quelques secondes."""
    if not server_date:
        return "Horloge : impossible à vérifier (pas d'en-tête Date)"
    server = parsedate_to_datetime(server_date)
    offset = (datetime.now(timezone.utc) - server).total_seconds()
    state = "OK" if abs(offset) <= 3 else "DÉCALÉE : synchronise l'heure de Windows"
    return f"Horloge du PC : {offset:+.0f} s par rapport au serveur -> {state}"


def main() -> None:
    print("1) Nœuds Hedera testnet (connexion TCP)\n")
    results = {}
    for host in HOSTS:
        for port, label in PORTS.items():
            ok = tcp_ok(host, port)
            results[(host, port)] = ok
            print(f"   {host}:{port} ({label}) -> {'OK' if ok else 'BLOQUÉ / TIMEOUT'}")

    print("\n2) Nœud miroir (HTTPS, port 443) et horloge du PC\n")
    try:
        with urllib.request.urlopen(
            "https://testnet.mirrornode.hedera.com/api/v1/network/nodes?limit=1", timeout=10
        ) as r:
            print(f"   HTTPS -> OK (code {r.status})")
            print("   " + clock_report(r.headers.get("Date")))
    except Exception as e:  # noqa: BLE001
        print(f"   HTTPS -> ÉCHEC ({type(e).__name__})")

    tls = any(ok for (h, p), ok in results.items() if p == 50212)
    plain = any(ok for (h, p), ok in results.items() if p == 50211)
    print("\nConclusion :")
    if tls:
        print("   Le port 50212 passe : relance hedera_submit.py (il réessaie sur d'autres nœuds).")
    elif plain:
        print("   Seul 50211 passe : ajoute HEDERA_TLS=0 dans .env puis relance hedera_submit.py.")
    else:
        print("   Ton réseau bloque Hedera. Change de réseau (partage de connexion du téléphone), VPN coupé, puis relance ce test.")


if __name__ == "__main__":
    main()
