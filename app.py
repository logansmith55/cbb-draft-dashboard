import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# =======================
# CONFIG
# =======================
API_KEY = st.secrets["CBBD_ACCESS_TOKEN"]
HEADERS = {"Authorization": f"Bearer {API_KEY}"}
CT = ZoneInfo("America/Chicago")

st.set_page_config(page_title="Metro Sharon CBB Draft Leaderboard", layout="wide")

# =======================
# DRAFT PICKS
# =======================
@st.cache_data(ttl=3600)
def load_draft_picks():
    return pd.DataFrame([
        # Doug
        [252,"Saint Louis","Doug"],[339,"Virginia","Doug"],[51,"Cincinnati","Doug"],
        [235,"Providence","Doug"],[118,"Illinois","Doug"],[87,"Florida","Doug"],[102,"Gonzaga","Doug"],
        # Evan
        [11,"Arizona","Evan"],[25,"Boise State","Evan"],[5,"Alabama","Evan"],
        [160,"Maryland","Evan"],[169,"Michigan State","Evan"],[248,"SMU","Evan"],[314,"UConn","Evan"],
        # Jack
        [72,"Duke","Jack"],[298,"Texas Tech","Jack"],[359,"Xavier","Jack"],
        [223,"Oregon","Jack"],[323,"USC","Jack"],[257,"San Diego State","Jack"],[12,"Arkansas","Jack"],
        # Logan
        [20,"Baylor","Logan"],[61,"Creighton","Logan"],[124,"Iowa","Logan"],
        [150,"Louisville","Logan"],[163,"Memphis","Logan"],[170,"Michigan","Logan"],[177,"Missouri","Logan"],
        # Mike
        [52,"Clemson","Mike"],[125,"Iowa State","Mike"],[34,"Butler","Mike"],
        [355,"Wisconsin","Mike"],[329,"Utah State","Mike"],[135,"Kentucky","Mike"],[253,"Saint Mary's","Mike"],
        # Nico
        [64,"Dayton","Nico"],[200,"North Carolina","Nico"],[113,"Houston","Nico"],
        [338,"Villanova","Nico"],[313,"UCLA","Nico"],[16,"Auburn","Nico"],[29,"Bradley","Nico"],
        # Nick
        [333,"VCU","Nick"],[185,"NC State","Nick"],[18,"BYU","Nick"],
        [279,"St. John's","Nick"],[121,"Indiana","Nick"],[216,"Ohio State","Nick"],[336,"Vanderbilt","Nick"],
        # Sam
        [342,"Wake Forest","Sam"],[131,"Kansas","Sam"],[157,"Marquette","Sam"],
        [65,"DePaul","Sam"],[236,"Purdue","Sam"],[292,"Tennessee","Sam"],[220,"Ole Miss","Sam"]
    ], columns=["team_id","school","person"])

# =======================
# API FETCH
# =======================
@st.cache_data(ttl=3600)
def fetch_games(draft_df):
    games = []
    for team in draft_df["school"].unique():
        r = requests.get(
            "https://api.collegebasketballdata.com/games",
            headers=HEADERS,
            params={
                "season": 2026,
                "team": team,
                "startDateRange": "2025-11-01",
                "endDateRange": "2026-12-31"
            }
        )
        if r.status_code == 200:
            games.extend(r.json())

    df = pd.DataFrame(games).drop_duplicates("id")
    df["startDate"] = pd.to_datetime(df["startDate"], utc=True).dt.tz_convert(CT)
    return df

# =======================
# PROCESS DATA
# =======================
@st.cache_data(ttl=3600)
def process_data(picks, games):
    records = {}

    for _, g in games.iterrows():
        if pd.isna(g.homePoints) or pd.isna(g.awayPoints):
            continue

        for t in [g.homeTeam, g.awayTeam]:
            records.setdefault(t, {"Wins":0,"Losses":0})

        if g.homePoints > g.awayPoints:
            records[g.homeTeam]["Wins"] += 1
            records[g.awayTeam]["Losses"] += 1
        else:
            records[g.awayTeam]["Wins"] += 1
            records[g.homeTeam]["Losses"] += 1

    standings = pd.DataFrame(records).T.reset_index().rename(columns={"index":"Team"})
    standings["Games"] = standings["Wins"] + standings["Losses"]

    # 🔒 ZERO-SAFE WIN %
    standings["Win Percentage"] = (
        standings["Wins"] / standings["Games"]
    ).fillna(0)

    # Google Sheets rounding
    standings["Win Percentage"] = (standings["Win Percentage"] * 10000).round() / 10000

    merged = picks.merge(standings, left_on="school", right_on="Team", how="left")
    merged[["Wins","Losses","Games","Win Percentage"]] = merged[
        ["Wins","Losses","Games","Win Percentage"]
    ].fillna(0)

    leaderboard = (
        merged.groupby("person")[["Wins","Losses","Games"]]
        .sum()
        .reset_index()
    )
    leaderboard["Win Percentage"] = (
        leaderboard["Wins"] / leaderboard["Games"]
    ).fillna(0)

    leaderboard["Win Percentage"] = (leaderboard["Win Percentage"] * 10000).round() / 10000

    return leaderboard, merged

# =======================
# APP
# =======================
st.title("Metro Sharon CBB Draft Leaderboard")

picks = load_draft_picks()
games = fetch_games(picks)
leaderboard, merged = process_data(picks, games)

st.caption(f"Last updated: {datetime.now(CT).strftime('%Y-%m-%d %I:%M %p CT')}")

# =======================
# OVERALL LEADERBOARD
# =======================
st.subheader("Overall Leaderboard")
lb = leaderboard.sort_values("Win Percentage", ascending=False).copy()
lb["Win Percentage"] = (lb["Win Percentage"] * 100).map("{:.2f}%".format)
st.dataframe(lb, use_container_width=True)

# =======================
# INDIVIDUAL LEADERBOARDS
# =======================
st.subheader("Individual Performance")

for person in lb["person"]:
    with st.expander(person):
        df = merged[merged.person == person].copy()
        df["Win Percentage"] = (df["Win Percentage"] * 100).map("{:.2f}%".format)
        st.dataframe(
            df[["school","Wins","Losses","Games","Win Percentage"]]
            .sort_values("Win Percentage", ascending=False),
            use_container_width=True
        )

# =======================
# DAILY SCOREBOARD
# =======================
st.subheader("Daily Scoreboard")

date = st.date_input("Select date", datetime.now(CT).date())
owners = dict(zip(picks.school, picks.person))

day = games[games.startDate.dt.date == date].copy()
day["homeOwner"] = day.homeTeam.map(owners)
day["awayOwner"] = day.awayTeam.map(owners)

def format_table(df):
    df["Time"] = df.startDate.dt.strftime("%I:%M %p")
    df["Home"] = df.homeTeam + " (" + df.homeOwner.fillna("") + ")"
    df["Away"] = df.awayTeam + " (" + df.awayOwner.fillna("") + ")"
    return df[["Time","Home","homePoints","Away","awayPoints"]]

# Big Games
big = day[day.homeOwner.notna() & day.awayOwner.notna() & (day.homeOwner != day.awayOwner)]
if not big.empty:
    st.markdown("### Big Games")
    st.dataframe(format_table(big), use_container_width=True)

# Per Person
for person in picks.person.unique():
    teams = picks[picks.person == person].school.tolist()
    person_games = day[
        day.homeTeam.isin(teams) | day.awayTeam.isin(teams)
    ]
    if not person_games.empty:
        st.markdown(f"### {person}")
        st.dataframe(format_table(person_games), use_container_width=True)
