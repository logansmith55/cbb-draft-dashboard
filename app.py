import streamlit as st
import pandas as pd
import cbbd
import datetime

# --- Configuration (adapt for Streamlit) ---
# For secure deployment, store your CBBD_ACCESS_TOKEN in Streamlit secrets or environment variables.
# Example for Streamlit secrets: CBBD_ACCESS_TOKEN = st.secrets["CBBD_ACCESS_TOKEN"]
# For local testing, you can directly assign your token here temporarily.
CBBD_ACCESS_TOKEN = st.secrets["CBBD_ACCESS_TOKEN"]
configuration = cbbd.Configuration(access_token=CBBD_ACCESS_TOKEN)

# --- Data Fetching and Processing Functions (cached for performance) ---
# @st.cache_data caches the return value of the function, so it only runs once unless inputs change
@st.cache_data
def load_draft_picks():
    columns = ["team_id", "school", "person"]
    draft = [
        [64, "Dayton", "Nico"], [252, "Saint Louis", "Doug"], [333, "VCU", "Nick"], [200, "North Carolina", "Nico"],
        [72, "Duke", "Jack"], [185, "NC State", "Nick"], [339, "Virginia", "Doug"], [342, "Wake Forest", "Sam"],
        [52, "Clemson", "Mike"], [150, "Louisville", "Logan"], [248, "SMU", "Evan"], [163, "Memphis", "Logan"],
        [131, "Kansas", "Sam"], [20, "Baylor", "Logan"], [125, "Iowa State", "Mike"], [298, "Texas Tech", "Jack"],
        [113, "Houston", "Nico"], [18, "BYU", "Nick"], [51, "Cincinnati", "Doug"], [11, "Arizona", "Evan"],
        [338, "Villanova", "Nico"], [279, "St. John's", "Nick"], [235, "Providence", "Doug"], [157, "Marquette", "Sam"],
        [61, "Creighton", "Logan"], [359, "Xavier", "Jack"], [65, "DePaul", "Sam"], [34, "Butler", "Mike"],
        [236, "Purdue", "Sam"], [121, "Indiana", "Nick"], [118, "Illinois", "Doug"], [216, "Ohio State", "Nick"],
        [124, "Iowa", "Logan"], [355, "Wisconsin", "Mike"], [170, "Michigan", "Logan"], [169, "Michigan State", "Evan"],
        [160, "Maryland", "Evan"], [223, "Oregon", "Jack"], [313, "UCLA", "Nico"], [323, "USC", "Jack"],
        [257, "San Diego State", "Jack"], [25, "Boise State", "Evan"], [329, "Utah State", "Mike"], [135, "Kentucky", "Mike"],
        [5, "Alabama", "Evan"], [292, "Tennessee", "Sam"], [87, "Florida", "Doug"], [336, "Vanderbilt", "Nick"],
        [16, "Auburn", "Nico"], [220, "Ole Miss", "Sam"], [12, "Arkansas", "Jack"], [177, "Missouri", "Logan"],
        [253, "Saint Mary's", "Mike"], [102, "Gonzaga", "Doug"], [314, "UConn", "Evan"], [29, "Bradley", "Nico"]
    ]
    return pd.DataFrame(draft, columns=columns)

@st.cache_data(ttl=3600)
def fetch_cbbd_data():
    config = cbbd.Configuration(
        access_token=st.secrets["CBBD_ACCESS_TOKEN"]
    )

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

@st.cache_data
def process_data(df_picks, df_teams, df_rankings, df_games):
    # Calculate team records
    team_records = {}
    for index, row in df_games.iterrows():
        home_team = row['homeTeam']
        away_team = row['awayTeam']
        home_points = row['homePoints']
        away_points = row['awayPoints']

        if home_team not in team_records: team_records[home_team] = {'Wins': 0, 'Losses': 0}
        if away_team not in team_records: team_records[away_team] = {'Wins': 0, 'Losses': 0}

        if home_points is not None and away_points is not None:
            if home_points > away_points:
                team_records[home_team]['Wins'] += 1
                team_records[away_team]['Losses'] += 1
            elif away_points > home_points:
                team_records[away_team]['Wins'] += 1
                team_records[home_team]['Losses'] += 1

    df_standings = pd.DataFrame.from_dict(team_records, orient='index')
    df_standings.index.name = 'Team'
    df_standings = df_standings.reset_index()

    # Calculate Win Percentage
    df_standings['Win Percentage'] = df_standings['Wins'] / (df_standings['Wins'] + df_standings['Losses'])

    # Calculate streaks
    df_games_sorted = df_games.sort_values(by='startDate', ascending=False).reset_index(drop=True)
    team_streaks = {}
    for index, row in df_games_sorted.iterrows():
        home_team = row['homeTeam']
        away_team = row['awayTeam']
        home_points = row['homePoints']
        away_points = row['awayPoints']

        if home_points is None or away_points is None or home_points == away_points:
            continue

        winner = None
        loser = None

        if home_points > away_points:
            winner = home_team
            loser = away_team
        else:
            winner = away_team
            loser = home_team

        if winner not in team_streaks: team_streaks[winner] = 'W1'
        else:
            if team_streaks[winner].startswith('W'): team_streaks[winner] = f'W{int(team_streaks[winner][1:]) + 1}'
            else: team_streaks[winner] = 'W1'

        if loser not in team_streaks: team_streaks[loser] = 'L1'
        else:
            if team_streaks[loser].startswith('L'): team_streaks[loser] = f'L{int(team_streaks[loser][1:]) + 1}'
            else: team_streaks[loser] = 'L1'

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')

    # Get next game info
    df_games['startDate'] = pd.to_datetime(df_games['startDate'])
    current_time = pd.to_datetime(datetime.datetime.now(datetime.timezone.utc))
    df_future_games = df_games[df_games['startDate'] > current_time]

    next_game_info = {}
    for team_name in df_standings['Team'].unique():
        team_future_games = df_future_games[(df_future_games['homeTeam'] == team_name) | (df_future_games['awayTeam'] == team_name)]
        if not team_future_games.empty:
            earliest_game = team_future_games.sort_values(by='startDate').iloc[0]
            opponent = earliest_game['awayTeam'] if earliest_game['homeTeam'] == team_name else earliest_game['homeTeam']
            next_game_info[team_name] = {'opponent': opponent, 'date': earliest_game['startDate'].strftime('%Y-%m-%d %H:%M')}

    df_standings['Next Game Opponent'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('opponent', 'N/A'))
    df_standings['Next Game Date'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('date', 'N/A'))

    # Merge with picks for drafter performance
    df_merged_picks_standings = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')
    df_drafter_performance = df_merged_picks_standings.groupby('person')['Win Percentage'].mean().reset_index()
    df_drafter_performance.rename(columns={'Win Percentage': 'Average Win Percentage'}, inplace=True)
    df_leaderboard = df_drafter_performance.sort_values(by='Average Win Percentage', ascending=False).reset_index(drop=True)

    df_drafter_stats = df_merged_picks_standings.groupby('person')[['Wins', 'Losses']].sum().reset_index()
    df_drafter_stats['Total Games Played'] = df_drafter_stats['Wins'] + df_drafter_stats['Losses']
    df_leaderboard = pd.merge(df_leaderboard, df_drafter_stats, on='person', how='left')

    df_leaderboard = df_leaderboard.drop(columns=['Wins_x', 'Losses_x', 'Total Games Played_x'], errors='ignore')
    df_leaderboard.rename(columns={'Wins_y': 'Wins', 'Losses_y': 'Losses', 'Total Games Played_y': 'Total Games Played'}, inplace=True)
    new_column_order = ['person', 'Wins', 'Losses', 'Total Games Played', 'Average Win Percentage']
    df_leaderboard = df_leaderboard[new_column_order]

    # Create team_games_df (team-level game log)
    home_games = df_games.copy()
    home_games['team_id'] = home_games['homeTeamId']
    home_games['opponent_id'] = home_games['awayTeamId']
    home_games['is_home'] = True
    home_games['points_scored'] = home_games['homePoints']
    home_games['points_allowed'] = home_games['awayPoints']

    away_games = df_games.copy()
    away_games['team_id'] = away_games['awayTeamId']
    away_games['opponent_id'] = away_games['homeTeamId']
    away_games['is_home'] = False
    away_games['points_scored'] = away_games['awayPoints']
    away_games['points_allowed'] = away_games['homePoints']

    team_games_df = pd.concat([home_games, away_games], ignore_index=True)
    team_games_df = team_games_df[[
        'id', 'season', 'startDate', 'team_id', 'opponent_id', 'is_home', 'points_scored', 'points_allowed'
    ]].rename(columns={'id': 'game_id', 'startDate': 'game_date'})

    team_games_df['points_scored'] = team_games_df['points_scored'].astype(int)
    team_games_df['points_allowed'] = team_games_df['points_allowed'].astype(int)
    team_games_df['season'] = team_games_df['season'].astype(int)
    team_games_df['game_date'] = pd.to_datetime(team_games_df['game_date'])
    team_games_df['win'] = team_games_df['points_scored'] > team_games_df['points_allowed']
    team_games_df['point_diff'] = team_games_df['points_scored'] - team_games_df['points_allowed']

    team_games_df = pd.merge(
        team_games_df,
        df_teams[['id', 'school', 'mascot', 'abbreviation', 'conference']],
        left_on='team_id', right_on='id', how='left'
    ).rename(columns={
        'school': 'team_name', 'mascot': 'team_mascot', 'abbreviation': 'team_abbreviation', 'conference': 'team_conference'
    }).drop(columns=['id'])

    team_games_df = pd.merge(
        team_games_df,
        df_teams[['id', 'school', 'mascot', 'abbreviation', 'conference']],
        left_on='opponent_id', right_on='id', how='left'
    ).rename(columns={
        'school': 'opponent_name', 'mascot': 'opponent_mascot', 'abbreviation': 'opponent_abbreviation', 'conference': 'opponent_conference'
    }).drop(columns=['id'])

    # Merge rankings into team_games_df
    team_games_df['game_date'] = pd.to_datetime(team_games_df['game_date'])
    df_rankings['pollDate'] = pd.to_datetime(df_rankings['pollDate'])

    team_games_df_sorted = team_games_df.sort_values(by=['game_date', 'team_id']).reset_index(drop=True)
    df_rankings_sorted = df_rankings.sort_values(by=['pollDate', 'teamId']).reset_index(drop=True)

    df_merged_rankings = pd.merge_asof(
        team_games_df_sorted,
        df_rankings_sorted[['pollDate', 'teamId', 'ranking', 'week']],
        left_on='game_date', right_on='pollDate', left_by='team_id', right_by='teamId',
        direction='backward', allow_exact_matches=True
    )
    df_merged_rankings.rename(columns={
        'ranking': 'team_ranking', 'week': 'ranking_week', 'pollDate': 'ranking_pollDate'
    }, inplace=True)

    df_merged_rankings = pd.merge_asof(
        df_merged_rankings,
        df_rankings_sorted[['pollDate', 'teamId', 'ranking', 'week']],
        left_on='game_date', right_on='pollDate', left_by='opponent_id', right_by='teamId',
        direction='backward', allow_exact_matches=True, suffixes=('_team', '_opponent')
    )
    df_merged_rankings.rename(columns={
        'ranking_opponent': 'opponent_ranking', 'week_opponent': 'opponent_ranking_week', 'pollDate_opponent': 'opponent_ranking_pollDate'
    }, inplace=True)

    return df_leaderboard, df_merged_picks_standings, df_merged_rankings

# --- Main Streamlit App Logic ---
st.title('CBB Draft Leaderboard')

# Load and process data
df_picks = load_draft_picks()
df_teams, df_rankings, df_games = fetch_cbbd_data()
df_leaderboard, df_merged_picks_standings, df_merged_rankings = process_data(df_picks, df_teams, df_rankings, df_games)

# Sort the data by 'Average Win Percentage' in descending order
leaderboard_data = df_leaderboard.sort_values(by='Average Win Percentage', ascending=False).reset_index(drop=True)

# Multi-select filter for 'person'
selected_persons = st.multiselect(
    'Filter by Person',
    options=leaderboard_data['person'].unique(),
    default=leaderboard_data['person'].unique()
)

# Filter the dataframe based on selected persons
filtered_leaderboard = leaderboard_data[leaderboard_data['person'].isin(selected_persons)]

# Display the filtered and sorted leaderboard
st.subheader('Overall Leaderboard')
st.dataframe(filtered_leaderboard)

# Display individual drafter details
st.subheader('Individual Drafter Performance')
for person_name in df_leaderboard['person'].unique():
    with st.expander(f"Teams drafted by {person_name}"):
        person_teams_df = df_merged_picks_standings[
            df_merged_picks_standings['person'] == person_name
        ][
            ['school', 'Wins', 'Losses', 'Win Percentage', 'Streak', 'Next Game Opponent', 'Next Game Date']
        ].sort_values(by='Win Percentage', ascending=False)

        # Handle potential division by zero if a person has no games played
        avg_win_pct = person_teams_df['Win Percentage'].mean() if not person_teams_df.empty else 0.0

        summary_row = pd.DataFrame([{
            'school': 'Total',
            'Wins': person_teams_df['Wins'].sum(),
            'Losses': person_teams_df['Losses'].sum(),
            'Win Percentage': avg_win_pct,
            'Streak': '',
            'Next Game Opponent': '',
            'Next Game Date': ''
        }])

        final_df = pd.concat([person_teams_df, summary_row], ignore_index=True)
        st.dataframe(final_df)

st.write("---")
st.markdown("""
**To run this Streamlit app:**
1.  Save the code above as a Python file (e.g., `app.py`).
2.  Install dependencies: `pip install streamlit pandas cbbd`
    *(Note: `PyGithub` was in the original notebook but is not used in this Streamlit app's logic.)*
3.  Set your `CBBD_ACCESS_TOKEN` securely (e.g., using Streamlit secrets if deploying to Streamlit Cloud, or environment variables).
    For local testing, you can temporarily replace `"YOUR_CBBD_ACCESS_TOKEN_HERE"` with your actual token.
4.  Execute `streamlit run app.py` in your terminal.

**Removed Colab/GitHub specific sections:**
*   `!pip install` commands (moved to instructions).
*   `google.colab` imports and `drive.mount` (Colab-specific).
*   `help()` calls (for debugging/inspection).
*   `.to_csv()` calls to Google Drive paths (Streamlit apps typically don't persist data to local files in this way).
*   GitHub API interaction for uploading files (sensitive tokens, and generally handled outside the live app logic).
*   `df.head()` calls (for display/debugging in notebooks, not for final script output).
""")
