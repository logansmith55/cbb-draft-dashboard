import streamlit as st
import pandas as pd
import requests
import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP

# =============================
# CONFIG
# =============================
API_KEY = st.secrets["CBBD_ACCESS_TOKEN"]
BASE_URL_GAMES = "https://api.collegebasketballdata.com/games"
BASE_URL_RANKINGS = "https://api.collegebasketballdata.com/rankings"
CENTRAL = ZoneInfo("America/Chicago")

st.set_page_config(page_title="Metro Sharon CBB Draft", layout="wide")

# =============================
# DRAFT PICKS
# =============================
@st.cache_data(ttl=86400)
def load_draft_picks():
    return pd.DataFrame(
        [
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
            [65,"DePaul","Sam"],[236,"Purdue","Sam"],[292,"Tennessee","Sam"],[220,"Ole Miss","Sam"],
        ],
        columns=["team_id","school","person"]
    )

# =============================
# FETCH GAMES (ONE CALL TOTAL)
# =============================
@st.cache_data(ttl=3600)
def fetch_games():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    params = {
        "season": 2026,
        "startDateRange": "2025-11-01",
        "endDateRange": "2026-12-31"
    }

    r = requests.get(BASE_URL_GAMES, headers=headers, params=params)

    if r.status_code != 200:
        st.error(f"Games API error {r.status_code}: {r.text}")
        return pd.DataFrame()

    df = pd.DataFrame(r.json())
    if df.empty:
        return df

    df["startDate"] = (
        pd.to_datetime(df["startDate"], utc=True)
        .dt.tz_convert(CENTRAL)
    )

    return df

# =============================
# FETCH RANKINGS (OPTIONAL)
# =============================
@st.cache_data(ttl=3600)
def fetch_rankings():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    r = requests.get(BASE_URL_RANKINGS, headers=headers, params={"season": 2026})
    if r.status_code != 200:
        return pd.DataFrame()
    return pd.DataFrame(r.json())

# =============================
# PROCESS DATA
# =============================
@st.cache_data(ttl=3600)
def process_data(df_picks, df_games, df_rankings):
    draft_teams = set(df_picks["school"])
    df_games = df_games[
        (df_games["homeTeam"].isin(draft_teams)) |
        (df_games["awayTeam"].isin(draft_teams))
    ].copy()

    # -------------------------
    # RECORDS
    # -------------------------
    records = {t:{"Wins":0,"Losses":0} for t in draft_teams}

    completed = df_games.dropna(subset=["homePoints","awayPoints"])
    for _,g in completed.iterrows():
        h,a = g["homeTeam"], g["awayTeam"]
        if g["homePoints"] > g["awayPoints"]:
            records[h]["Wins"] += 1
            records[a]["Losses"] += 1
        elif g["awayPoints"] > g["homePoints"]:
            records[a]["Wins"] += 1
            records[h]["Losses"] += 1

    df_team = pd.DataFrame.from_dict(records, orient="index").reset_index()
    df_team.rename(columns={"index":"school"}, inplace=True)

    # Win %
    df_team["WinPct"] = df_team.apply(
        lambda r: Decimal(r.Wins) / Decimal(r.Wins+r.Losses)
        if r.Wins+r.Losses>0 else Decimal(0),
        axis=1
    )

    # -------------------------
    # STREAKS (MOST RECENT FIRST)
    # -------------------------
    df_games_sorted = completed.sort_values("startDate", ascending=False)
    streaks = {}

    for _,g in df_games_sorted.iterrows():
        h,a = g["homeTeam"], g["awayTeam"]
        winner = h if g["homePoints"]>g["awayPoints"] else a
        loser  = a if winner==h else h

        if winner not in streaks:
            streaks[winner] = "W1"
        elif streaks[winner].startswith("W"):
            streaks[winner] = f"W{int(streaks[winner][1:])+1}"

        if loser not in streaks:
            streaks[loser] = "L1"
        elif streaks[loser].startswith("L"):
            streaks[loser] = f"L{int(streaks[loser][1:])+1}"

    df_team["Streak"] = df_team["school"].map(streaks).fillna("N/A")

    # -------------------------
    # MERGE PICKS
    # -------------------------
    df_merged = df_picks.merge(df_team, on="school", how="left")

    # -------------------------
    # RANKINGS (SAFE)
    # -------------------------
    if not df_rankings.empty:
        latest = df_rankings.sort_values("pollDate").drop_duplicates("teamId", keep="last")
        rank_map = dict(zip(latest.teamId, latest.ranking))
        df_merged["Ranking"] = df_merged["team_id"].map(rank_map)
        df_merged["school_display"] = df_merged.apply(
            lambda r: f"{r.school} ({int(r.Ranking)})" if pd.notna(r.Ranking) else r.school,
            axis=1
        )
    else:
        df_merged["school_display"] = df_merged["school"]

    # -------------------------
    # INDIVIDUAL LEADERBOARD
    # -------------------------
    df_lb = (
        df_merged.groupby("person")[["Wins","Losses"]]
        .sum()
        .reset_index()
    )

    df_lb["WinPct"] = df_lb.apply(
        lambda r: (
            Decimal(r.Wins) / Decimal(r.Wins+r.Losses)
        ).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        if r.Wins+r.Losses>0 else Decimal(0),
        axis=1
    )

    return df_lb, df_merged, df_games

# =============================
# DAILY SCOREBOARD
# =============================
def render_daily_scoreboard(df_games, df_picks, selected_date, persons):
    df = df_games[df_games["startDate"].dt.date == selected_date]
    team_to_person = dict(zip(df_picks.school, df_picks.person))

    big_games = []
    per_person = {p:[] for p in persons}

    for _,g in df.iterrows():
        h,a = g.homeTeam, g.awayTeam
        hp,ap = g.homePoints, g.awayPoints
        ph,pa = team_to_person.get(h), team_to_person.get(a)

        row = {
            "Home": h,
            "Home Score": hp,
            "Away": a,
            "Away Score": ap,
            "Time": g.startDate.strftime("%-I:%M %p")
        }

        if ph and pa:
            big_games.append(row)

        for p in persons:
            if ph==p or pa==p:
                per_person[p].append(row)

    def style(df):
        def f(r):
            s=[""]*len(r)
            if pd.notna(r["Home Score"]) and pd.notna(r["Away Score"]):
                if r["Home Score"]>r["Away Score"]:
                    s[0]=s[1]="background:#d4edda"
                    s[2]=s[3]="background:#f8d7da"
                elif r["Away Score"]>r["Home Score"]:
                    s[0]=s[1]="background:#f8d7da"
                    s[2]=s[3]="background:#d4edda"
            return s
        return df.style.apply(f, axis=1)

    if big_games:
        st.subheader("🔥 Big Games")
        st.dataframe(style(pd.DataFrame(big_games)), use_container_width=True)

    for p,rows in per_person.items():
        if rows:
            st.subheader(p)
            st.dataframe(style(pd.DataFrame(rows)), use_container_width=True)

# =============================
# APP
# =============================
tab1, tab2 = st.tabs(["Leaderboard","Daily Scoreboard"])

df_picks = load_draft_picks()
df_games = fetch_games()
df_rankings = fetch_rankings()

df_lb, df_merged, df_games = process_data(df_picks, df_games, df_rankings)

with tab1:
    st.title("Metro Sharon CBB Draft Leaderboard")
    st.caption(f"Updated {datetime.datetime.now(CENTRAL).strftime('%Y-%m-%d %I:%M %p')} CT")

    st.subheader("Overall Leaderboard")
    out = df_lb.copy()
    out["Win %"] = out["WinPct"].apply(lambda x: f"{(x*100).quantize(Decimal('0.01'))}%")
    st.dataframe(out.sort_values("WinPct", ascending=False), use_container_width=True)

    st.subheader("Individual Teams")
    for p in out.person:
        with st.expander(p):
            t = df_merged[df_merged.person==p][
                ["school_display","Wins","Losses","Streak","WinPct"]
            ].copy()
            t["Win %"] = t["WinPct"].apply(lambda x: f"{(x*100).quantize(Decimal('0.01'))}%")
            st.dataframe(t.drop(columns="WinPct"), use_container_width=True)

with tab2:
    st.subheader("Daily Scoreboard")
    today = datetime.datetime.now(CENTRAL).date()
    date = st.date_input("Date", today)
    people = sorted(df_picks.person.unique())
    render_daily_scoreboard(df_games, df_picks, date, people)
