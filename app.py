import streamlit as st
import pandas as pd
import cbbd
import datetime
from zoneinfo import ZoneInfo

# Access token setup (CBBD_ACCESS_TOKEN is stored in Streamlit settings)
CBBD_ACCESS_TOKEN = st.secrets["CBBD_ACCESS_TOKEN"]
configuration = cbbd.Configuration(access_token=CBBD_ACCESS_TOKEN)

# Populate draft picks for mapping
@st.cache_data(ttl=3600)
def load_draft_picks():
    columns = ["team_id", "school", "person"]

    draft = [
        # Doug
        [252, "Saint Louis", "Doug"],
        [339, "Virginia", "Doug"],
        [51, "Cincinnati", "Doug"],
        [235, "Providence", "Doug"],
        [118, "Illinois", "Doug"],
        [87, "Florida", "Doug"],
        [102, "Gonzaga", "Doug"],

        # Evan
        [11, "Arizona", "Evan"],
        [25, "Boise State", "Evan"],
        [5, "Alabama", "Evan"],
        [160, "Maryland", "Evan"],
        [169, "Michigan State", "Evan"],
        [248, "SMU", "Evan"],
        [314, "UConn", "Evan"],

        # Jack
        [72, "Duke", "Jack"],
        [298, "Texas Tech", "Jack"],
        [359, "Xavier", "Jack"],
        [223, "Oregon", "Jack"],
        [323, "USC", "Jack"],
        [257, "San Diego State", "Jack"],
        [12, "Arkansas", "Jack"],

        # Logan
        [20, "Baylor", "Logan"],
        [61, "Creighton", "Logan"],
        [124, "Iowa", "Logan"],
        [150, "Louisville", "Logan"],
        [163, "Memphis", "Logan"],
        [170, "Michigan", "Logan"],
        [177, "Missouri", "Logan"],

        # Mike
        [52, "Clemson", "Mike"],
        [125, "Iowa State", "Mike"],
        [34, "Butler", "Mike"],
        [355, "Wisconsin", "Mike"],
        [329, "Utah State", "Mike"],
        [135, "Kentucky", "Mike"],
        [253, "Saint Mary's", "Mike"],

        # Nico
        [64, "Dayton", "Nico"],
        [200, "North Carolina", "Nico"],
        [113, "Houston", "Nico"],
        [338, "Villanova", "Nico"],
        [313, "UCLA", "Nico"],
        [16, "Auburn", "Nico"],
        [29, "Bradley", "Nico"],

        # Nick
        [333, "VCU", "Nick"],
        [185, "NC State", "Nick"],
        [18, "BYU", "Nick"],
        [279, "St. John's", "Nick"],
        [121, "Indiana", "Nick"],
        [216, "Ohio State", "Nick"],
        [336, "Vanderbilt", "Nick"],

        # Sam
        [342, "Wake Forest", "Sam"],
        [131, "Kansas", "Sam"],
        [157, "Marquette", "Sam"],
        [65, "DePaul", "Sam"],
        [236, "Purdue", "Sam"],
        [292, "Tennessee", "Sam"],
        [220, "Ole Miss", "Sam"]
    ]
    return pd.DataFrame(draft, columns=columns)

# Fetch data from cbbd source
@st.cache_data(ttl=3600)
def fetch_cbbd_data():
    config = cbbd.Configuration(
        access_token=st.secrets["CBBD_ACCESS_TOKEN"] # stored in Streamlit
    )

    with cbbd.ApiClient(config) as api_client:
        # all college basketball teams
        teams_api = cbbd.TeamsApi(api_client)
        teams = teams_api.get_teams()
        df_teams = pd.DataFrame([team.to_dict() for team in teams])

        # AP and Coaches poll rankings
        rankings_api = cbbd.RankingsApi(api_client)
        rankings = rankings_api.get_rankings(season=2026)
        df_rankings = pd.DataFrame([rank.to_dict() for rank in rankings])

        # game level data
        games_api = cbbd.api.games_api.GamesApi(api_client)
        games = games_api.get_games(season=2026)
        df_games = pd.DataFrame([game.to_dict() for game in games])

    return df_teams, df_rankings, df_games

# Process data
@st.cache_data(ttl=3600)
def process_data(df_picks, df_teams, df_rankings, df_games):
    # Team records
    team_records = {}
    for _, row in df_games.iterrows():
        home_team = row['homeTeam']
        away_team = row['awayTeam']
        home_points = row['homePoints']
        away_points = row['awayPoints']

        if home_team not in team_records: team_records[home_team] = {'Wins':0,'Losses':0}
        if away_team not in team_records: team_records[away_team] = {'Wins':0,'Losses':0}

        if home_points is not None and away_points is not None:
            if home_points > away_points:
                team_records[home_team]['Wins'] += 1
                team_records[away_team]['Losses'] += 1
            elif away_points > home_points:
                team_records[away_team]['Wins'] += 1
                team_records[home_team]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index').reset_index().rename(columns={'index':'Team'})
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])

    # Calculate streaks
    df_games_sorted = df_games.sort_values(by='startDate', ascending=False).reset_index(drop=True)
    team_streaks = {}
    for _, row in df_games_sorted.iterrows():
        home_team, away_team = row['homeTeam'], row['awayTeam']
        home_points, away_points = row['homePoints'], row['awayPoints']

        if home_points is None or away_points is None or home_points==away_points:
            continue

        if home_points > away_points:
            winner, loser = home_team, away_team
        else:
            winner, loser = away_team, home_team

        # Winner streak
        if winner not in team_streaks: team_streaks[winner]='W1'
        else: team_streaks[winner] = f"W{int(team_streaks[winner][1:])+1}" if team_streaks[winner].startswith('W') else 'W1'

        # Loser streak
        if loser not in team_streaks: team_streaks[loser]='L1'
        else: team_streaks[loser] = f"L{int(team_streaks[loser][1:])+1}" if team_streaks[loser].startswith('L') else 'L1'

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')

    # Merge with picks
    df_merged = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')
    df_drafter_perf = df_merged.groupby('person')['Win Percentage'].mean().reset_index()
    df_leaderboard = df_drafter_perf.sort_values(by='Win Percentage', ascending=False).reset_index(drop=True)

    df_stats = df_merged.groupby('person')[['Wins','Losses']].sum().reset_index()
    df_stats['Total Games Played'] = df_stats['Wins'] + df_stats['Losses']
    df_leaderboard = pd.merge(df_leaderboard, df_stats, on='person', how='left')
    df_leaderboard = df_leaderboard[['person','Wins','Losses','Total Games Played','Win Percentage']]

    return df_leaderboard, df_merged

# --- Main Streamlit App ---
st.title('Metro Sharon CBB Draft Leaderboard')

df_picks = load_draft_picks()
df_teams, df_rankings, df_games = fetch_cbbd_data()
df_leaderboard, df_merged = process_data(df_picks, df_teams, df_rankings, df_games)

# Display latest game date
if not df_games.empty and 'startDate' in df_games.columns:
    df_games['startDate'] = pd.to_datetime(df_games['startDate'], errors='coerce')
    valid_dates = df_games['startDate'].dropna()
    if not valid_dates.empty:
        latest_game_date = valid_dates.max()
        if latest_game_date.tzinfo is None:
            latest_game_date = latest_game_date.replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo("America/Chicago"))
        else:
            latest_game_date = latest_game_date.astimezone(ZoneInfo("America/Chicago"))
        st.caption(f"Game data as of: {latest_game_date.strftime('%Y-%m-%d %H:%M %Z')}")
    else:
        st.caption("Game data as of: N/A")
else:
    st.caption("Game data as of: N/A")

st.caption(f"Last updated: {datetime.datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')}")

# Filter leaderboard by person
selected_persons = st.multiselect('Filter by Person', options=df_leaderboard['person'].unique(), default=df_leaderboard['person'].unique())
filtered_leaderboard = df_leaderboard[df_leaderboard['person'].isin(selected_persons)].copy()
filtered_leaderboard['Win Percentage'] = (filtered_leaderboard['Win Percentage']*100).round(2).astype(str) + '%'

st.subheader('Overall Leaderboard')
st.dataframe(filtered_leaderboard)

# Helper to sort streaks for display
def streak_sort_value(streak):
    if streak.startswith('W'): return int(streak[1:])
    if streak.startswith('L'): return -int(streak[1:])
    return 0

st.subheader('Individual Performance')
for person_name in df_leaderboard['person'].unique():
    with st.expander(f"{person_name}'s Teams"):
        person_df = df_merged[df_merged['person']==person_name][['school','Wins','Losses','Streak','Win Percentage']].copy()

        # Add total row
        avg_pct = person_df['Win Percentage'].mean() if not person_df.empty else 0
        avg_pct_display = round(avg_pct*100,2)
        summary_row = pd.DataFrame([{
            'school':'Total',
            'Wins':person_df['Wins'].sum(),
            'Losses':person_df['Losses'].sum(),
            'Streak':'',
            'Win Percentage': f"{avg_pct_display:.2f}%"
        }])

        # Convert each team's win% to display
        person_df['Win Percentage'] = (person_df['Win Percentage']*100).round(2).astype(str)+'%'

        final_df = pd.concat([person_df, summary_row], ignore_index=True)

        # Sort by streak for display only
        final_df_display = final_df.sort_values(by='Streak', key=lambda col: col.apply(streak_sort_value), ascending=False)

        st.dataframe(final_df_display)
