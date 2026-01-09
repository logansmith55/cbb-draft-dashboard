import streamlit as st
import pandas as pd
import requests
from zoneinfo import ZoneInfo
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP

st.set_page_config(page_title="Metro Sharon CBB Draft Leaderboard", layout="wide")

# =========================
# CONFIG
# =========================
API_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
CENTRAL = ZoneInfo("America/Chicago")

# =========================
# DATA
# =========================
@st.cache_data(ttl=3600)
def load_draft_picks():
    return pd.DataFrame([
        ["Purdue", "Sam"],
        ["Houston", "Nico"],
        ["Florida", "Doug"],
        ["UConn", "Evan"],
        ["Kentucky", "Mike"],
        ["Duke", "Jack"],
        ["St. John's", "Nick"],
        ["Marquette", "Logan"],
    ], columns=["school", "person"])


@st.cache_data(ttl=3600)
def fetch_team_records():
    url = f"{API_BASE}/teams"
    teams = []

    for page in range(1, 15):
        r = requests.get(url, params={"page": page}).json()
        for t in r.get("sports", [])[0]["leagues"][0]["teams"]:
            team = t["team"]
            record = team.get("record", {}).get("items", [{}])[0].get("summary", "0-0")
            wins, losses = map(int, record.split("-"))
            teams.append({
                "school": team["displayName"],
                "Wins": wins,
                "Losses": losses,
                "Streak": team.get("record", {}).get("items", [{}])[0].get("streak", {}).get("summary", "")
            })

    return pd.DataFrame(teams)


@st.cache_data(ttl=600)
def fetch_games():
    r = requests.get(f"{API_BASE}/scoreboard").json()
    games = []

    for e in r.get("events", []):
        comp = e["competitions"][0]
        start = pd.to_datetime(comp["date"], utc=True).tz_convert(CENTRAL)

        home, away = comp["competitors"]
        games.append({
            "date": start.date(),
            "time": start.strftime("%I:%M %p"),
            "home": home["team"]["displayName"],
            "away": away["team"]["displayName"],
            "home_score": int(home.get("score", 0)),
            "away_score": int(away.get("score", 0)),
            "status": comp["status"]["type"]["state"]
        })

    return pd.DataFrame(games)


# =========================
# PROCESSING
# =========================
@st.cache_data(ttl=600)
def process_data(df_picks, df_teams, df_games):
    df = df_picks.merge(df_teams, on="school", how="left").fillna(0)

    leaderboard = (
        df.groupby("person", as_index=False)
        .agg({"Wins": "sum", "Losses": "sum"})
    )

    leaderboard["WinPctNum"] = leaderboard.apply(
        lambda r: Decimal(r["Wins"]) / Decimal(r["Wins"] + r["Losses"])
        if r["Wins"] + r["Losses"] > 0 else Decimal(0),
        axis=1
    )

    leaderboard["Win Percentage"] = leaderboard["WinPctNum"].apply(
        lambda x: f"{(x*100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%"
    )

    leaderboard = leaderboard.sort_values("WinPctNum", ascending=False)

    return leaderboard, df


# =========================
# STYLES
# =========================
def highlight_scores(row):
    styles = [""] * len(row)

    if row["home_score"] > row["away_score"]:
        styles[row.index.get_loc("home_score")] = "background-color:#d4f7d4"
        styles[row.index.get_loc("away_score")] = "background-color:#f7d4d4"
    elif row["away_score"] > row["home_score"]:
        styles[row.index.get_loc("away_score")] = "background-color:#d4f7d4"
        styles[row.index.get_loc("home_score")] = "background-color:#f7d4d4"

    return styles


# =========================
# APP
# =========================
df_picks = load_draft_picks()
df_teams = fetch_team_records()
df_games = fetch_games()

leaderboard, merged = process_data(df_picks, df_teams, df_games)

st.title("🏀 Metro Sharon CBB Draft Leaderboard")

tab1, tab2 = st.tabs(["🏆 Standings", "📅 Daily Scoreboard"])

# =========================
# STANDINGS
# =========================
with tab1:
    st.subheader("Overall Leaderboard")
    st.dataframe(
        leaderboard[["person", "Wins", "Losses", "Win Percentage"]],
        use_container_width=True
    )

    st.divider()

    st.subheader("Individual Leaderboards")

    for person in df_picks["person"].unique():
        st.markdown(f"### {person}")
        person_df = merged[merged["person"] == person]

        total_wins = person_df["Wins"].sum()
        total_losses = person_df["Losses"].sum()

        pct = (
            Decimal(total_wins) / Decimal(total_wins + total_losses)
            if total_wins + total_losses > 0 else Decimal(0)
        )
        pct = (pct * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        summary = pd.DataFrame([{
            "school": "TOTAL",
            "Wins": total_wins,
            "Losses": total_losses,
            "Win Percentage": f"{pct}%"
        }])

        st.dataframe(
            pd.concat([
                person_df[["school", "Wins", "Losses"]],
                summary
            ]),
            use_container_width=True
        )


# =========================
# DAILY SCOREBOARD
# =========================
with tab2:
    st.subheader("Daily Scoreboard")

    selected_date = st.date_input("Select Date", value=date.today())
    selected_people = st.multiselect(
        "Filter by Person",
        options=df_picks["person"].unique(),
        default=df_picks["person"].unique()
    )

    games_today = df_games[df_games["date"] == selected_date]

    picks_map = df_picks.set_index("school")["person"].to_dict()

    games_today["home_person"] = games_today["home"].map(picks_map)
    games_today["away_person"] = games_today["away"].map(picks_map)

    big_games = games_today[
        games_today["home_person"].notna() &
        games_today["away_person"].notna()
    ]

    if not big_games.empty:
        st.markdown("## 🔥 Big Games")
        st.dataframe(
            big_games[[
                "time", "away", "away_person", "away_score",
                "home", "home_person", "home_score"
            ]].style.apply(highlight_scores, axis=1),
            use_container_width=True
        )

    for person in selected_people:
        person_games = games_today[
            (games_today["home_person"] == person) |
            (games_today["away_person"] == person)
        ]

        if person_games.empty:
            continue

        st.markdown(f"## {person}")

        display = person_games.copy()
        display["away"] = display["away"] + display["away_person"].apply(
            lambda x: f" ({x})" if pd.notna(x) else ""
        )
        display["home"] = display["home"] + display["home_person"].apply(
            lambda x: f" ({x})" if pd.notna(x) else ""
        )

        st.dataframe(
            display[[
                "time", "away", "away_score",
                "home", "home_score"
            ]].style.apply(highlight_scores, axis=1),
            use_container_width=True
        )
