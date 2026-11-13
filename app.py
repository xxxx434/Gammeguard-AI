
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from evidence import verify
from verify_onchain import fetch_records

st.set_page_config(
    page_title="GameGuard AI",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ GameGuard AI")
st.caption("Anti-cheat monitoring and Hedera evidence verification")

BASE = Path(__file__).resolve().parent
THRESHOLD = 70


def load_players():
    path = BASE / "players.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def get_topic():
    path = BASE / "topic_id.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


@st.cache_data(ttl=15)
def get_chain_records(topic_id):
    return fetch_records(topic_id)


def latest_record(player_id, records):
    matches = [
        (record, timestamp, sequence)
        for record, timestamp, sequence in records
        if record.get("player_id") == player_id
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: item[2])


players = load_players()
topic_id = get_topic()

with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Choose a page",
        ["Dashboard", "Players", "Verify Evidence"],
    )

    st.divider()
    st.subheader("Hedera Network")
    st.write("Network: Testnet")

    if topic_id:
        st.code(topic_id)
        st.link_button(
            "View on HashScan",
            f"https://hashscan.io/testnet/topic/{topic_id}",
        )
    else:
        st.warning("topic_id.txt not found")


if page == "Dashboard":
    st.header("Security Overview")

    total = len(players)
    suspicious = sum(
        p.get("suspicion_score", 0) >= THRESHOLD
        for p in players
    )

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Players", total)
    col2.metric("Suspicious Players", suspicious)
    col3.metric("Normal Players", total - suspicious)

    if players:
        df = pd.DataFrame(players)

        st.subheader("Suspicion Scores")

        chart = df.set_index("player_id")[
            ["suspicion_score"]
        ]
        st.bar_chart(chart)

        st.subheader("Players Overview")
        st.dataframe(
            df[
                [
                    "player_id",
                    "accuracy",
                    "reaction_ms",
                    "headshot_ratio",
                    "suspicion_score",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning(
            "players.json not found. Run your player simulation first."
        )


elif page == "Players":
    st.header("Player Investigation")

    if not players:
        st.warning("No players available.")
    else:
        selected_id = st.selectbox(
            "Select a player",
            [p["player_id"] for p in players],
        )

        player = next(
            p for p in players
            if p["player_id"] == selected_id
        )

        score = player["suspicion_score"]

        st.subheader(f"Player {selected_id}")
        st.metric("Suspicion Score", f"{score}/100")
        st.progress(min(max(score, 0), 100) / 100)

        if score >= THRESHOLD:
            st.error("Suspicious gameplay detected")
        else:
            st.success("No suspicious behavior detected")

        c1, c2, c3 = st.columns(3)
        c1.metric("Accuracy", f"{player['accuracy']:.0%}")
        c2.metric("Reaction Time", f"{player['reaction_ms']} ms")
        c3.metric(
            "Headshot Ratio",
            f"{player['headshot_ratio']:.0%}",
        )

        st.subheader("Detection Indicators")
        if player.get("indicators"):
            for indicator in player["indicators"]:
                st.warning(indicator)
        else:
            st.info("No indicators detected")


elif page == "Verify Evidence":
    st.header("Hedera Evidence Verification")

    st.write(
        "Upload an evidence JSON file to check whether "
        "it matches a signed record published on Hedera."
    )

    uploaded = st.file_uploader(
        "Upload evidence JSON",
        type=["json"],
    )

    if uploaded is not None:
        try:
            evidence = json.load(uploaded)
            player_id = evidence["player_id"]

            st.write("Player:", player_id)

            if not topic_id:
                st.error(
                    "Missing topic_id.txt. "
                    "Cannot verify against Hedera."
                )
            else:
                with st.spinner("Fetching Hedera records..."):
                    records = get_chain_records(topic_id)

                match = latest_record(player_id, records)

                if match is None:
                    st.error(
                        "No on-chain record found for this player."
                    )
                else:
                    record, timestamp, sequence = match
                    valid, message = verify(evidence, record)

                    if valid:
                        st.success("Evidence integrity verified!")
                    else:
                        st.error("Evidence verification FAILED!")

                    st.write("Verification result:", message)
                    st.write("Hedera sequence:", sequence)
                    st.write("Consensus timestamp:", timestamp)

                    st.link_button(
                        "Inspect on HashScan",
                        f"https://hashscan.io/testnet/topic/{topic_id}",
                    )

        except Exception as exc:
            st.error(f"Verification error: {exc}")

st.divider()
st.caption(
    "GameGuard AI | Hackathon Demo | "
    "Simulated gameplay data | Hedera Testnet"
)
