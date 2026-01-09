import streamlit as st
import pandas as pd
import cbbd
import datetime
from zoneinfo import ZoneInfo
import os
import shutil

# --- Clear CBBD cache to force fresh download ---
def clear_cbbd_cache():
    cache_dir = os.path.expanduser("~/.cbbd")
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)

# Run this every time before fetching
clear_cbbd_cache()

# --- Access token setup ---
CBBD_ACCESS_TOKEN = st.secrets["CBBD_ACCESS_TOKEN"]
configuration = cbbd.Configuration(access_token=CBBD_ACCESS_TOKEN)

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

# --- Fetch fresh CBBD data ---
def fetch_cbbd_data():
    config = cbbd.Configuration(access_token=CBBD_ACCESS_TOKEN)
    with cbbd.ApiClient(config) as api_client:
        teams_api = cbbd.TeamsApi(api_client)
        teams = teams_api.get_teams()
        df_teams = pd.DataFrame([team.to_dict() for team in teams])

        rankings_api = cbbd.RankingsApi(api_client)
        rankings = rankings_api.get_rankings(season=2026)
        df_rankings = pd.DataFrame([rank.to_dict() for rank in rankings])

        games_api = cbbd.api.games_api.GamesApi(api_client)
        games = games_api.get_games(season=2026)
        df_games = pd.DataFrame([game.to_dict() for game in games])

    return df_teams, df_rankings, df_games

# --- Process data (same as your code) ---
def add_streak_emoji(streak):
    if streak.startswith('W'):
        num = int(streak[1:])
        return f"{streak}🔥" if num >= 3 else streak
    elif streak.startswith('L'):
        num = int(streak[1:])
        return f"{streak}🥶" if num >= 3 else streak
    else:
        return streak

def process_data(df_picks, df_teams, df_rankings, df_games):
    # --- Team records ---
    team_records = {}
    for _, row in df_games.iterrows():
        home, away, home_pts, away_pts = row['homeTeam'], row['awayTeam'], row['homePoints'], row['awayPoints']
        if home not in team_records: team_records[home] = {'Wins': 0, 'Losses': 0}
        if away not in team_records: team_records[away] = {'Wins': 0, 'Losses': 0}
        if pd.notna(home_pts) and pd.notna(away_pts):
            if home_pts > away_pts:
                team_records[home]['Wins'] += 1; team_records[away]['Losses'] += 1
            elif away_pts > home_pts:
                team_records[away]['Wins'] += 1; team_records[home]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index().rename(columns={'index': 'Team'})
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])

    # --- Streaks ---
    df_games_sorted = df_games.sort_values(by='startDate', ascending=False).reset_index(drop=True)
    team_streaks = {}
    for _, row in df_games_sorted.iterrows():
        home_team, away_team = row['homeTeam'], row['awayTeam']
        home_pts, away_pts = row['homePoints'], row['awayPoints']
        if home_pts is None or away_pts is None or home_pts == away_pts: continue

        winner, loser = (home_team, away_team) if home_pts > away_pts else (away_team, home_team)

        team_streaks[winner] = f"W{int(team_streaks[winner][1:])+1}" if winner in team_streaks and team_streaks[winner].startswith('W') else 'W1'
        team_streaks[loser] = f"L{int(team_streaks[loser][1:])+1}" if loser in team_streaks and team_streaks[loser].startswith('L') else 'L1'

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')
    df_standings['Streak'] = df_standings['Streak'].apply(add_streak_emoji)

    # --- Next games ---
    df_games['startDate'] = pd.to_datetime(df_games['startDate'])
    now = pd.to_datetime(datetime.datetime.now(datetime.timezone.utc))
    df_future_games = df_games[df_games['startDate'] > now]
    next_game_info = {}
    for team in df_standings['Team']:
        future_games = df_future_games[(df_future_games['homeTeam']==team) | (df_future_games['awayTeam']==team)]
        if not future_games.empty:
            next_game = future_games.sort_values('startDate').iloc[0]
            opponent = next_game['awayTeam'] if next_game['homeTeam']==team else next_game['homeTeam']
            next_game_info[team] = {'opponent': opponent, 'date': next_game['startDate'].strftime('%Y-%m-%d %H:%M')}
    df_standings['Next Game Opponent'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('opponent','N/A'))
    df_standings['Next Game Date'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('date','N/A'))

    # --- Merge picks and leaderboard ---
    df_merged = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')
    df_leaderboard = df_merged.groupby('person')['Win Percentage'].mean().reset_index()
    stats = df_merged.groupby('person')[['Wins','Losses']].sum().reset_index()
    stats['Total Games Played'] = stats['Wins'] + stats['Losses']
    df_leaderboard = pd.merge(df_leaderboard, stats, on='person', how='left')
    df_leaderboard = df_leaderboard[['person','Wins','Losses','Total Games Played','Win Percentage']]

    # --- Latest AP ranking ---
    latest_rankings = df_rankings.sort_values('pollDate').drop_duplicates('teamId', keep='last')
    team_rank_map = dict(zip(latest_rankings['teamId'], latest_rankings['ranking']))
    df_merged = pd.merge(df_merged, df_teams[['school','id']], left_on='school', right_on='school', how='left')
    df_merged['Ranking'] = df_merged['id'].map(team_rank_map)
    df_merged['school_with_rank'] = df_merged.apply(
        lambda row: f"{row['school']} ({int(row['Ranking'])})" if pd.notna(row['Ranking']) else row['school'], axis=1
    )

    return df_leaderboard, df_merged

# --- Main Streamlit ---
st.title("Metro Sharon CBB Draft Leaderboard")

df_picks = load_draft_picks()
df_teams, df_rankings, df_games = fetch_cbbd_data()
df_leaderboard, df_merged_picks_standings = process_data(df_picks, df_teams, df_rankings, df_games)

# Display last update time
st.caption(f"Last updated: {datetime.datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')}")

# Leaderboard
leaderboard_data = df_leaderboard.sort_values('Win Percentage', ascending=False).reset_index(drop=True)
selected_persons = st.multiselect("Filter by Person", options=leaderboard_data['person'].unique(), default=leaderboard_data['person'].unique())
filtered_leaderboard = leaderboard_data[leaderboard_data['person'].isin(selected_persons)]
filtered_leaderboard['Win Percentage'] = filtered_leaderboard['Win Percentage'].apply(lambda x: f"{x*100:.2f}%")
st.subheader("Overall Leaderboard")
st.dataframe(filtered_leaderboard)
