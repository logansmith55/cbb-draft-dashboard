import streamlit as st
import pandas as pd
import requests
import datetime
from zoneinfo import ZoneInfo

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

# --- Add streak emojis ---
def add_streak_emoji(streak):
    if streak.startswith('W'):
        return f"{streak}🔥" if int(streak[1:]) >= 3 else streak
    elif streak.startswith('L'):
        return f"{streak}🥶" if int(streak[1:]) >= 3 else streak
    else:
        return streak

# --- Fetch data from API ---
def fetch_api(url, params=None):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()

@st.cache_data(ttl=3600)
def fetch_teams():
    return pd.DataFrame(fetch_api(BASE_URL_TEAMS))

@st.cache_data(ttl=3600)
def fetch_rankings():
    return pd.DataFrame(fetch_api(BASE_URL_RANKINGS, params={"season": 2026}))

@st.cache_data(ttl=3600)
def fetch_games():
    df_picks = load_draft_picks()
    all_games = []
    for team in df_picks["school"].unique():
        params = {
            "season": 2026,
            "team": team,
            "startDateRange": "2025-11-01",
            "endDateRange": "2026-12-31"
        }
        all_games.extend(fetch_api(BASE_URL_GAMES, params=params))
    return pd.DataFrame(all_games).drop_duplicates(subset="id")

# --- Process data ---
@st.cache_data(ttl=3600)
def process_data(df_picks, df_teams, df_rankings, df_games):
    # --- Team records ---
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

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index().rename(columns={'index':'Team'})
    df_standings['Win Percentage'] = df_standings.apply(
        lambda row: round(row['Wins'] / (row['Wins'] + row['Losses']), 4) if (row['Wins'] + row['Losses']) > 0 else 0,
        axis=1
    )

    # --- Calculate streaks chronologically ---
    df_games_sorted = df_games.sort_values('startDate', ascending=True)
    streaks = {}
    for _, row in df_games_sorted.iterrows():
        if pd.isna(row['homePoints']) or pd.isna(row['awayPoints']) or row['homePoints'] == row['awayPoints']:
            continue
        winner, loser = (row['homeTeam'], row['awayTeam']) if row['homePoints'] > row['awayPoints'] else (row['awayTeam'], row['homeTeam'])

        # Winner streak
        streaks[winner] = f"W{int(streaks[winner][1:])+1}" if winner in streaks and streaks[winner].startswith('W') else "W1"
        # Loser streak
        streaks[loser] = f"L{int(streaks[loser][1:])+1}" if loser in streaks and streaks[loser].startswith('L') else "L1"

    df_standings['Streak'] = df_standings['Team'].map(streaks).fillna('N/A')
    df_standings['Streak'] = df_standings['Streak'].apply(add_streak_emoji)

    # --- Next game info ---
    df_games['startDate'] = pd.to_datetime(df_games['startDate'])
    now = pd.to_datetime(datetime.datetime.now(datetime.timezone.utc))
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

    # --- Merge picks ---
    df_merged = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')

    # --- Individual leaderboard (correct calculation) ---
    stats = df_merged.groupby('person')[['Wins','Losses']].sum().reset_index()
    stats['Total Games Played'] = stats['Wins'] + stats['Losses']
    stats['Win Percentage'] = stats.apply(
        lambda row: round(row['Wins'] / row['Total Games Played'], 4) if row['Total Games Played'] > 0 else 0,
        axis=1
    )
    df_leaderboard = stats[['person','Wins','Losses','Total Games Played','Win Percentage']]

    # --- Add latest ranking ---
    latest_rankings = df_rankings.sort_values('pollDate').drop_duplicates('teamId', keep='last')
    team_rank_map = dict(zip(latest_rankings['teamId'], latest_rankings['ranking']))
    df_merged = pd.merge(df_merged, df_teams[['school','id']], left_on='school', right_on='school', how='left')
    df_merged['Ranking'] = df_merged['id'].map(team_rank_map)
    df_merged['school_with_rank'] = df_merged.apply(
        lambda row: f"{row['school']} ({int(row['Ranking'])})" if pd.notna(row['Ranking']) else row['school'], axis=1
    )

    return df_leaderboard, df_merged

# --- Streamlit App ---
st.title("Metro Sharon CBB Draft Leaderboard")

df_picks = load_draft_picks()
df_teams = fetch_teams()
df_rankings = fetch_rankings()
df_games = fetch_games()
df_leaderboard, df_merged = process_data(df_picks, df_teams, df_rankings, df_games)

st.caption(f"Last updated: {datetime.datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')}")

# --- Leaderboard ---
leaderboard_data = df_leaderboard.sort_values('Win Percentage', ascending=False).reset_index(drop=True)
leaderboard_data['Win Percentage'] = leaderboard_data['Win Percentage'].apply(lambda x: f"{x*100:.2f}%")
st.subheader("Overall Leaderboard")
st.dataframe(leaderboard_data)

# --- Individual Performance ---
st.subheader("Individual Performance")
for person in df_leaderboard['person'].unique():
    with st.expander(f"{person}'s Teams"):
        person_df = df_merged[df_merged['person']==person][
            ['school_with_rank','Wins','Losses','Streak','Win Percentage']
        ].sort_values('Win Percentage', ascending=False)
        person_df = person_df.rename(columns={'school_with_rank':'school'})
        avg_win_pct = round(person_df['Wins'].sum() / max(1, (person_df['Wins'].sum()+person_df['Losses'].sum())),4)*100
        person_df['Win Percentage'] = person_df['Win Percentage'].apply(lambda x: f"{x*100:.2f}%")
        summary = pd.DataFrame([{
            'school':'Total',
            'Wins': person_df['Wins'].sum(),
            'Losses': person_df['Losses'].sum(),
            'Streak':'',
            'Win Percentage': f"{avg_win_pct:.2f}%"
        }])
        st.dataframe(pd.concat([person_df, summary], ignore_index=True))
