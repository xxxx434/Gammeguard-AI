
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from evidence import verify
from verify_onchain import fetch_records


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="GameGuard AI",
    page_icon="🛡️",
    layout="wide",
)

BASE = Path(__file__).resolve().parent
THRESHOLD = 70

# Translate indicators stored in French in players.json
INDICATOR_TRANSLATIONS = {
    "précision anormalement élevée": "Abnormally high shooting accuracy",
    "temps de réaction quasi impossible": "Extremely fast reaction time",
    "taux de tirs à la tête anormal": "Abnormally high headshot ratio",
}


def translate_indicator(indicator):
    return INDICATOR_TRANSLATIONS.get(indicator, indicator)


def load_players():
    path = BASE / "players.json"

    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


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


# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

players = load_players()
topic_id = get_topic()

total_players = len(players)

suspicious_players = sum(
    p.get("suspicion_score", 0) >= THRESHOLD
    for p in players
)

normal_players = total_players - suspicious_players


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.title("🛡️ GameGuard AI")

    st.caption("Intelligent Anti-Cheat Monitoring")

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Player Investigation",
            "Hedera Verification",
        ],
    )

    st.divider()

    st.subheader("Blockchain Network")

    st.write("Network: Hedera Testnet")

    if topic_id:

        st.success("Hedera Topic Connected")

        st.code(topic_id)

        st.link_button(
            "View on HashScan",
            f"https://hashscan.io/testnet/topic/{topic_id}",
        )

    else:
        st.warning("Hedera topic ID not found")


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if page == "Dashboard":

    st.title("Security Monitoring Dashboard")

    st.write(
        "Monitor simulated player behavior, identify suspicious "
        "activity, and investigate potential cheating."
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Players",
        total_players,
    )

    col2.metric(
        "Suspicious Players",
        suspicious_players,
    )

    col3.metric(
        "Normal Players",
        normal_players,
    )

    st.divider()

    if players:

        df = pd.DataFrame(players)

        st.subheader("Player Suspicion Scores")

        chart_data = df.set_index("player_id")[
            ["suspicion_score"]
        ]

        st.bar_chart(chart_data)

        st.subheader("Player Monitoring Table")

        display_df = df[
            [
                "player_id",
                "accuracy",
                "reaction_ms",
                "headshot_ratio",
                "suspicion_score",
            ]
        ].copy()

        display_df["status"] = display_df[
            "suspicion_score"
        ].apply(
            lambda score: (
                "Suspicious"
                if score >= THRESHOLD
                else "Normal"
            )
        )

        display_df.columns = [
            "Player ID",
            "Accuracy",
            "Reaction Time (ms)",
            "Headshot Ratio",
            "Suspicion Score",
            "Status",
        ]

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        st.info(
            "Suspicion scores are generated using predefined "
            "behavioral detection rules. They are not "
            "probabilities of cheating."
        )

    else:

        st.warning(
            "No player data found. "
            "Please generate players.json first."
        )


# --------------------------------------------------
# PLAYER INVESTIGATION
# --------------------------------------------------

elif page == "Player Investigation":

    st.title("Player Investigation Center")

    st.write(
        "Analyze individual player statistics and "
        "review suspicious gameplay indicators."
    )

    st.divider()

    if not players:

        st.warning("No player data available.")

    else:

        selected_id = st.selectbox(
            "Select a Player",
            [p["player_id"] for p in players],
        )

        player = next(
            p for p in players
            if p["player_id"] == selected_id
        )

        score = player["suspicion_score"]

        st.subheader(f"Player Profile: {selected_id}")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Shooting Accuracy",
            f"{player['accuracy']:.0%}",
        )

        col2.metric(
            "Reaction Time",
            f"{player['reaction_ms']} ms",
        )

        col3.metric(
            "Headshot Ratio",
            f"{player['headshot_ratio']:.0%}",
        )

        st.divider()

        st.subheader("Suspicion Analysis")

        st.metric(
            "Suspicion Score",
            f"{score}/100",
        )

        st.progress(
            min(max(score, 0), 100) / 100
        )

        if score >= THRESHOLD:

            st.error(
                "High-risk behavior detected. "
                "Further investigation recommended."
            )

        elif score >= 40:

            st.warning(
                "Moderate suspicion. "
                "Additional monitoring recommended."
            )

        else:

            st.success(
                "No significant suspicious behavior detected."
            )

        st.subheader("Detected Behavioral Indicators")

        indicators = player.get("indicators", [])

        if indicators:

            for indicator in indicators:

                st.warning(
                    translate_indicator(indicator)
                )

        else:

            st.info(
                "No suspicious behavioral indicators detected."
            )

        st.caption(
            "Detection is based on simulated gameplay "
            "statistics and predefined rules."
        )


# --------------------------------------------------
# HEDERA VERIFICATION
# --------------------------------------------------

elif page == "Hedera Verification":

    st.title("Blockchain Evidence Verification")

    st.write(
        "Verify whether gameplay evidence matches "
        "a signed record published on Hedera Testnet."
    )

    st.divider()

    st.subheader("Upload Evidence")

    uploaded_file = st.file_uploader(
        "Select an evidence JSON file",
        type=["json"],
    )

    if uploaded_file is not None:

        try:

            evidence = json.load(uploaded_file)

            player_id = evidence["player_id"]

            st.info(
                f"Evidence uploaded for player {player_id}"
            )

            if not topic_id:

                st.error(
                    "Hedera topic ID is missing. "
                    "Blockchain verification is unavailable."
                )

            else:

                with st.spinner(
                    "Retrieving evidence records from Hedera..."
                ):

                    records = get_chain_records(topic_id)

                match = latest_record(
                    player_id,
                    records,
                )

                if match is None:

                    st.error(
                        "No matching blockchain record was found "
                        "for this player."
                    )

                else:

                    record, timestamp, sequence = match

                    valid, message = verify(
                        evidence,
                        record,
                    )

                    st.divider()

                    st.subheader("Verification Results")

                    if valid:

                        st.success(
                            "EVIDENCE VERIFIED"
                        )

                        st.write(
                            "The uploaded evidence matches "
                            "the signed record published on Hedera."
                        )

                    else:

                        st.error(
                            "EVIDENCE VERIFICATION FAILED"
                        )

                        st.write(
                            "The uploaded evidence does not match "
                            "the blockchain record or its signature "
                            "is invalid."
                        )

                    st.write(
                        "Player ID:",
                        player_id,
                    )

                    st.write(
                        "Hedera Sequence Number:",
                        sequence,
                    )

                    st.write(
                        "Consensus Timestamp:",
                        timestamp,
                    )

                    st.write(
                        "SHA-256 Evidence Hash:",
                        record.get("sha256", "Unavailable"),
                    )

                    st.link_button(
                        "Inspect Record on HashScan",
                        f"https://hashscan.io/testnet/topic/{topic_id}",
                    )

                    st.caption(
                        "Verification confirms evidence integrity "
                        "against the retrieved blockchain record. "
                        "It does not independently establish "
                        "whether the player cheated."
                    )

        except Exception as error:

            st.error(
                f"Unable to verify evidence: {error}"
            )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "GameGuard AI | AI & Web3 Hackathon Demo | "
    "Simulated Anti-Cheat Detection | Hedera Testnet"
)
