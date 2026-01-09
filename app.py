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
def process_data(df_picks, df_teams, df_rankings, df_games):
    # Team records
    team_records = {}
    for _, row in df_games.iterrows():
        home, away, home_pts, away_pts = row['homeTeam'], row['awayTeam'], row['homePoints'], row['awayPoints']
        if home not in team_records: team_records[home] = {"Wins": 0, "Losses": 0}
        if away not in team_records: team_records[away] = {"Wins": 0, "Losses": 0}
        if pd.notna(home_pts) and pd.notna(away_pts):
            if home_pts > away_pts:
                team_records[home]["Wins"] += 1
                team_records[away]["Losses"] += 1
            elif away_pts > home_pts:
                team_records[away]["Wins"] += 1
                team_records[home]["Losses"] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index().rename(columns={'index': 'Team'})
    df_standings['Win Percentage'] = df_standings.apply(
        lambda row: Decimal(row['Wins']) / Decimal(row['Wins'] + row['Losses']) if (row['Wins']+row['Losses'])>0 else Decimal(0), axis=1
    )

    # Streaks
    df_games_sorted = df_games.sort_values('startDate', ascending=True)
    team_streaks = {}
    for _, row in df_games_sorted.iterrows():
        home_team, away_team = row['homeTeam'], row['awayTeam']
        home_pts, away_pts = row['homePoints'], row['awayPoints']
        if home_pts is None or away_pts is None or home_pts==away_pts:
            continue
        winner, loser = (home_team, away_team) if home_pts>away_pts else (away_team, home_team)
        team_streaks[winner] = f"W{int(team_streaks[winner][1:])+1}" if winner in team_streaks and team_streaks[winner].startswith('W') else "W1"
        team_streaks[loser] = f"L{int(team_streaks[loser][1:])+1}" if loser in team_streaks and team_streaks[loser].startswith('L') else "L1"

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')
    df_standings['Streak'] = df_standings['Streak'].apply(add_streak_emoji)

    # Next game
    now = pd.to_datetime(datetime.datetime.now(ZoneInfo('America/Chicago')))
    df_future_games = df_games[df_games['startDate'] > now]
    next_game_info = {}
    for team in df_standings['Team']:
        future_games = df_future_games[(df_future_games['homeTeam']==team) | (df_future_games['awayTeam']==team)]
        if not future_games.empty:
            next_game = future_games.sort_values('startDate').iloc[0]
            opponent = next_game['awayTeam'] if next_game['homeTeam']==team else next_game['homeTeam']
            next_game_info[team] = {"opponent": opponent, "date": next_game['startDate'].strftime("%Y-%m-%d %H:%M")}
    df_standings['Next Game Opponent'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('opponent','N/A'))
    df_standings['Next Game Date'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('date','N/A'))

    # Merge picks
    df_merged = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')

    # Individual leaderboard
    df_leaderboard = df_merged.groupby('person').agg({
        'Wins':'sum',
        'Losses':'sum',
    }).reset_index()
    df_leaderboard['Total Games Played'] = df_leaderboard['Wins'] + df_leaderboard['Losses']
    df_leaderboard['Win Percentage'] = df_leaderboard.apply(lambda r: format_win_pct(r['Wins'], r['Losses']), axis=1)

    # Latest ranking
    latest_rankings = df_rankings.sort_values('pollDate').drop_duplicates('teamId', keep='last')
    team_rank_map = dict(zip(latest_rankings['teamId'], latest_rankings['ranking']))
    df_merged = pd.merge(df_merged, df_teams[['school','id']], left_on='school', right_on='school', how='left')
    df_merged['Ranking'] = df_merged['id'].map(team_rank_map)
    df_merged['school_with_rank'] = df_merged.apply(
        lambda row: f"{row['school']} ({int(row['Ranking'])})" if pd.notna(row['Ranking']) else row['school'], axis=1
    )

    return df_leaderboard, df_merged

# --- Daily scoreboard ---
def generate_daily_scoreboard(df_games, df_picks, selected_date, selected_persons):
    df_games['startDate'] = pd.to_datetime(df_games['startDate']).dt.tz_convert(ZoneInfo('America/Chicago'))
    date_games = df_games[df_games['startDate'].dt.date == selected_date]
    df_picks_filtered = df_picks[df_picks['person'].isin(selected_persons)]
    team_person_map = dict(zip(df_picks_filtered['school'], df_picks_filtered['person']))

    # Prepare Big Games and Individual games
    big_games, individual_games = [], {person: [] for person in selected_persons}
    for _, row in date_games.iterrows():
        home, away = row['homeTeam'], row['awayTeam']
        home_pts, away_pts = row['homePoints'], row['awayPoints']
        home_person = team_person_map.get(home)
        away_person = team_person_map.get(away)

        game_info = {
            "Home Team": home,
            "Home Score": home_pts if pd.notna(home_pts) else "",
            "Home Person": home_person if home_person else "",
            "Away Team": away,
            "Away Score": away_pts if pd.notna(away_pts) else "",
            "Away Person": away_person if away_person else "",
            "Time": row['startDate'].strftime("%H:%M")
        }

        if home_person and away_person:
            big_games.append(game_info)

        for person in selected_persons:
            if (home_person==person or away_person==person):
                individual_games[person].append(game_info)

    # Big Games table
    if big_games:
        st.subheader("Big Games")
        big_df = pd.DataFrame([{
            "Home Team": f"{g['Home Team']} ({g['Home Person']})",
            "Home Score": g["Home Score"],
            "Away Team": f"{g['Away Team']} ({g['Away Person']})",
            "Away Score": g["Away Score"],
            "Time": g["Time"]
        } for g in big_games])
        st.dataframe(big_df)

    # Individual tables per person
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
            st.dataframe(person_df)

# --- Streamlit App ---
tab1, tab2 = st.tabs(["Leaderboard","Daily Scoreboard"])

with tab1:
    st.title("Metro Sharon CBB Draft Leaderboard")
    df_picks = load_draft_picks()
    df_teams = fetch_teams()
    df_rankings = fetch_rankings()
    df_games = fetch_games()
    df_leaderboard, df_merged = process_data(df_picks, df_teams, df_rankings, df_games)

    st.caption(f"Last updated: {datetime.datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')}")
    st.subheader("Overall Leaderboard")
    st.dataframe(df_leaderboard.sort_values('Win Percentage', ascending=False).reset_index(drop=True))

    st.subheader("Individual Performance")
    for person in df_leaderboard['person']:
        with st.expander(f"{person}'s Teams"):
            person_df = df_merged[df_merged['person']==person][
                ['school_with_rank','Wins','Losses','Streak','Win Percentage']
            ].sort_values('Win Percentage', ascending=False)
            person_df = person_df.rename(columns={'school_with_rank':'school'})
            avg_win_pct = Decimal(person_df['Win Percentage'].mean() if not person_df.empty else 0)
            avg_win_pct = avg_win_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            person_df['Win Percentage'] = person_df['Win Percentage'].apply(lambda x: f"{Decimal(x*100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%")
            summary = pd.DataFrame([{
                'school':'Total',
                'Wins': person_df['Wins'].sum(),
                'Losses': person_df['Losses'].sum(),
                'Streak':'',
                'Win Percentage': f"{avg_win_pct}%"
            }])
            st.dataframe(pd.concat([person_df, summary], ignore_index=True))

with tab2:
    st.subheader("Daily Scoreboard")
    df_picks = load_draft_picks()
    df_games = fetch_games()
    today = datetime.datetime.now(ZoneInfo("America/Chicago")).date()
    selected_date = st.date_input("Select Date", value=today)
    persons = sorted(df_picks['person'].unique())
    selected_persons = st.multiselect("Filter by Person", options=persons, default=persons)
    generate_daily_scoreboard(df_games, df_picks, selected_date, selected_persons)
