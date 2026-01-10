import streamlit as st
import pandas as pd
import requests
import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP

# --- Secrets ---
API_KEY = st.secrets["CBBD_ACCESS_TOKEN"]
BASE_URL_GAMES = "https://api.collegebasketballdata.com/games"
BASE_URL_TEAMS = "https://api.collegebasketballdata.com/teams"
BASE_URL_RANKINGS = "https://api.collegebasketballdata.com/rankings"

# --- Draft picks ---
@st.cache_data(ttl=3600)
def load_draft_picks():
    columns = ["team_id", "school", "person"]
    draft = [
        # Doug
        [252, "Saint Louis", "Doug"], [339, "Virginia", "Doug"], [51, "Cincinnati", "Doug"],
        [235, "Providence", "Doug"], [118, "Illinois", "Doug"], [87, "Florida", "Doug"], [102, "Gonzaga", "Doug"],
        # Evan
        [11, "Arizona", "Evan"], [25, "Boise State", "Evan"], [5, "Alabama", "Evan"],
        [160, "Maryland", "Evan"], [169, "Michigan State", "Evan"], [248, "SMU", "Evan"], [314, "UConn", "Evan"],
        # Jack
        [72, "Duke", "Jack"], [298, "Texas Tech", "Jack"], [359, "Xavier", "Jack"],
        [223, "Oregon", "Jack"], [323, "USC", "Jack"], [257, "San Diego State", "Jack"], [12, "Arkansas", "Jack"],
        # Logan
        [20, "Baylor", "Logan"], [61, "Creighton", "Logan"], [124, "Iowa", "Logan"],
        [150, "Louisville", "Logan"], [163, "Memphis", "Logan"], [170, "Michigan", "Logan"], [177, "Missouri", "Logan"],
        # Mike
        [52, "Clemson", "Mike"], [125, "Iowa State", "Mike"], [34, "Butler", "Mike"],
        [355, "Wisconsin", "Mike"], [329, "Utah State", "Mike"], [135, "Kentucky", "Mike"], [253, "Saint Mary's", "Mike"],
        # Nico
        [64, "Dayton", "Nico"], [200, "North Carolina", "Nico"], [113, "Houston", "Nico"],
        [338, "Villanova", "Nico"], [313, "UCLA", "Nico"], [16, "Auburn", "Nico"], [29, "Bradley", "Nico"],
        # Nick
        [333, "VCU", "Nick"], [185, "NC State", "Nick"], [18, "BYU", "Nick"],
        [279, "St. John's", "Nick"], [121, "Indiana", "Nick"], [216, "Ohio State", "Nick"], [336, "Vanderbilt", "Nick"],
        # Sam
        [342, "Wake Forest", "Sam"], [131, "Kansas", "Sam"], [157, "Marquette", "Sam"],
        [65, "DePaul", "Sam"], [236, "Purdue", "Sam"], [292, "Tennessee", "Sam"], [220, "Ole Miss", "Sam"]
    ]
    return pd.DataFrame(draft, columns=columns)

# --- Helper functions ---
def add_streak_emoji(streak):
    if streak.startswith('W'):
        num = int(streak[1:])
        return f"{streak}🔥" if num >= 3 else streak
    elif streak.startswith('L'):
        num = int(streak[1:])
        return f"{streak}🥶" if num >= 3 else streak
    else:
        return streak

def format_win_pct(wins, losses):
    if wins + losses == 0:
        return "0.00%"
    pct = Decimal(wins) / Decimal(wins + losses) * Decimal(100)
    pct = pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{pct}%"

def format_game_time(dt):
    return dt.strftime("%-I:%M %p")  # 12-hour with AM/PM

# --- Fetch functions ---
@st.cache_data(ttl=3600)
def fetch_teams():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(BASE_URL_TEAMS, headers=headers)
    response.raise_for_status()
    return pd.DataFrame(response.json())

@st.cache_data(ttl=3600)
def fetch_rankings():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(BASE_URL_RANKINGS, headers=headers, params={"season": 2026})
    response.raise_for_status()
    return pd.DataFrame(response.json())

@st.cache_data(ttl=3600)
def fetch_games():
    df_picks = load_draft_picks()
    draft_teams = df_picks["school"].unique()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    all_games = []

    for team in draft_teams:
        params = {
            "season": 2026,
            "team": team,
            "startDateRange": "2025-11-01",
            "endDateRange": "2026-12-31"
        }
        response = requests.get(BASE_URL_GAMES, headers=headers, params=params)
        if response.status_code == 200:
            all_games.extend(response.json())
        else:
            st.warning(f"Error fetching games for {team}: {response.text}")

    df_games = pd.DataFrame(all_games).drop_duplicates(subset="id")
    df_games['startDate'] = pd.to_datetime(df_games['startDate']).dt.tz_convert(ZoneInfo('America/Chicago'))
    return df_games

# --- Process leaderboard ---
@st.cache_data(ttl=3600)
def process_data(df_picks, df_games, df_rankings):
    # Initialize team records
    records = {team: {"Wins":0, "Losses":0} for team in df_picks["school"].unique()}

    # Compute wins/losses safely
    for _, row in df_games.iterrows():
        h = row['homeTeam']
        a = row['awayTeam']
        h_pts = row['homePoints']
        a_pts = row['awayPoints']

        if pd.notna(h_pts) and pd.notna(a_pts):
            if h_pts > a_pts and h in records:
                records[h]["Wins"] += 1
            if a_pts > h_pts and a in records:
                records[a]["Wins"] += 1
            if h_pts < a_pts and h in records:
                records[h]["Losses"] += 1
            if a_pts < h_pts and a in records:
                records[a]["Losses"] += 1

    # Build standings
    df_standings = pd.DataFrame.from_dict(records, orient='index').reset_index().rename(columns={'index':'Team'})
    df_standings['Win Percentage'] = df_standings.apply(
        lambda r: (r['Wins'] / (r['Wins'] + r['Losses'])) if (r['Wins']+r['Losses'])>0 else 0, axis=1
    )

    # Add streaks
    df_games_sorted = df_games.sort_values('startDate')
    streaks = {}
    for _, row in df_games_sorted.iterrows():
        h = row['homeTeam']
        a = row['awayTeam']
        h_pts = row['homePoints']
        a_pts = row['awayPoints']

        if pd.isna(h_pts) or pd.isna(a_pts) or h_pts==a_pts:
            continue

        winner, loser = (h, a) if h_pts>a_pts else (a, h)
        streaks[winner] = f"W{int(streaks[winner][1:])+1}" if winner in streaks and streaks[winner].startswith('W') else "W1"
        streaks[loser] = f"L{int(streaks[loser][1:])+1}" if loser in streaks and streaks[loser].startswith('L') else "L1"

    df_standings['Streak'] = df_standings['Team'].map(streaks).fillna('N/A').apply(add_streak_emoji)

    # Merge with picks for individual leaderboard
    df_merged = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')

    # Individual leaderboard
    df_lb = df_merged.groupby('person').agg({'Wins':'sum','Losses':'sum'}).reset_index()
    df_lb['Total Games Played'] = df_lb['Wins'] + df_lb['Losses']
    df_lb['Win Percentage'] = df_lb.apply(lambda r: format_win_pct(r['Wins'], r['Losses']), axis=1)

    return df_lb, df_merged, df_games

# --- Daily scoreboard ---
def generate_daily_scoreboard(df_games, df_picks, selected_date, selected_persons):
    df_games['startDate'] = pd.to_datetime(df_games['startDate']).dt.tz_convert(ZoneInfo('America/Chicago'))
    date_games = df_games[df_games['startDate'].dt.date==selected_date]

    team_person_map = dict(zip(df_picks['school'], df_picks['person']))
    big_games = []
    individual_games = {person: [] for person in selected_persons}

    for _, row in date_games.iterrows():
        h = row['homeTeam']
        a = row['awayTeam']
        h_pts = row['homePoints']
        a_pts = row['awayPoints']
        h_person = team_person_map.get(h)
        a_person = team_person_map.get(a)

        game_info = {
            "Home Team": h, "Home Score": h_pts, "Home Person": h_person,
            "Away Team": a, "Away Score": a_pts, "Away Person": a_person,
            "Time": row['startDate'].strftime("%-I:%M %p")
        }

        if h_person and a_person:
            big_games.append(game_info)
        for person in selected_persons:
            if h_person==person or a_person==person:
                individual_games[person].append(game_info)

    # Color highlighting
    def style_colors(df):
        def highlight(row):
            style = ['']*len(row)
            h_pts = row['Home Score']
            a_pts = row['Away Score']
            if pd.notna(h_pts) and pd.notna(a_pts):
                if h_pts > a_pts:
                    style[0] = style[1] = 'background-color: #d4edda'
                    style[2] = style[3] = 'background-color: #f8d7da'
                elif a_pts > h_pts:
                    style[0] = style[1] = 'background-color: #f8d7da'
                    style[2] = style[3] = 'background-color: #d4edda'
            return style
        return df.style.apply(highlight, axis=1)

    # Big Games
    if big_games:
        st.subheader("Big Games")
        big_df = pd.DataFrame([{
            "Home Team": f"{g['Home Team']} ({g['Home Person']})",
            "Home Score": g["Home Score"],
            "Away Team": f"{g['Away Team']} ({g['Away Person']})",
            "Away Score": g["Away Score"],
            "Time": g["Time"]
        } for g in big_games])
        st.dataframe(style_colors(big_df))

    # Individual tables
    for person, games in individual_games.items():
        if games:
            st.subheader(person)
            person_df = pd.DataFrame([{
                "Home Team": f"{g['Home Team']} ({g['Home Person']})" if g['Home Person']==person else g['Home Team'],
                "Home Score": g["Home Score"],
                "Away Team": f"{g['Away Team']} ({g['Away Person']})" if g['Away Person']==person else g['Away Team'],
                "Away Score": g["Away Score"],
                "Time": g["Time"]
            } for g in games])
            st.dataframe(style_colors(person_df))

# --- Streamlit App ---
tab1, tab2 = st.tabs(["Leaderboard","Daily Scoreboard"])

with tab1:
    st.title("Metro Sharon CBB Draft Leaderboard")
    df_picks = load_draft_picks()
    df_rankings = fetch_rankings()
    df_lb, df_merged, df_games = process_data(df_picks, fetch_games(), df_rankings)

    st.caption(f"Last updated: {datetime.datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %I:%M %p %Z')}")
    st.subheader("Overall Leaderboard")
    st.dataframe(df_lb.sort_values('Win Percentage', ascending=False).reset_index(drop=True))

    st.subheader("Individual Performance")
    for person in df_lb['person']:
        with st.expander(f"{person}'s Teams"):
            person_df = df_merged[df_merged['person']==person][['school','Wins','Losses','Streak','Win Percentage']].sort_values('Win Percentage', ascending=False)
            avg_win_pct = Decimal(person_df['Win Percentage'].mean() if not person_df.empty else 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            person_df['Win Percentage'] = person_df['Win Percentage'].apply(lambda x: f"{Decimal(x*100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%")
            summary = pd.DataFrame([{'school':'Total','Wins': person_df['Wins'].sum(),'Losses': person_df['Losses'].sum(),'Streak':'','Win Percentage': f"{avg_win_pct}%"}])
            st.dataframe(pd.concat([person_df, summary], ignore_index=True))

with tab2:
    st.subheader("Daily Scoreboard")
    df_picks = load_draft_picks()
    df_games = fetch_games()
    today = datetime.datetime.now(ZoneInfo("America/Chicago")).date()
    selected_date = st.date_input("Select Date", value=today)
    persons = sorted(df_picks['person'].unique())
    selected_person = st.selectbox("Select Person (or All)", options=["All"]+persons, index=0)
    selected_persons = persons if selected_person=="All" else [selected_person]
    generate_daily_scoreboard(df_games, df_picks, selected_date, selected_persons)
