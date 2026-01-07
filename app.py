import streamlit as st
import pandas as pd
import cbbd
import datetime
from zoneinfo import ZoneInfo

# Access token setup (CBBD_ACCESS_TOKEN is stored in Streamlit settings)
CBBD_ACCESS_TOKEN = st.secrets["CBBD_ACCESS_TOKEN"]
configuration = cbbd.Configuration(access_token=CBBD_ACCESS_TOKEN)

# --- Populate draft picks for mapping ---
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


# --- Get data from CBBD source ---
@st.cache_data(ttl=3600)
def fetch_cbbd_data():
    config = cbbd.Configuration(
        access_token=st.secrets["CBBD_ACCESS_TOKEN"]
    )
    with cbbd.ApiClient(config) as api_client:
        # All college basketball teams
        teams_api = cbbd.TeamsApi(api_client)
        teams = teams_api.get_teams()
        df_teams = pd.DataFrame([team.to_dict() for team in teams])

        # AP and Coaches poll rankings
        rankings_api = cbbd.RankingsApi(api_client)
        rankings = rankings_api.get_rankings(season=2026)
        df_rankings = pd.DataFrame([rank.to_dict() for rank in rankings])

        # Game-level data
        games_api = cbbd.api.games_api.GamesApi(api_client)
        games = games_api.get_games(season=2026)
        df_games = pd.DataFrame([game.to_dict() for game in games])

    return df_teams, df_rankings, df_games


# --- Process data ---
@st.cache_data(ttl=3600)
def process_data(df_picks, df_teams, df_rankings, df_games):
    # Calculate team records
    team_records = {}
    for _, row in df_games.iterrows():
        home_team = row['homeTeam']
        away_team = row['awayTeam']
        home_points = row['homePoints']
        away_points = row['awayPoints']

        if home_team not in team_records:
            team_records[home_team] = {'Wins': 0, 'Losses': 0}
        if away_team not in team_records:
            team_records[away_team] = {'Wins': 0, 'Losses': 0}

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
    for _, row in df_games_sorted.iterrows():
        home_team = row['homeTeam']
        away_team = row['awayTeam']
        home_points = row['homePoints']
        away_points = row['awayPoints']

        if home_points is None or away_points is None or home_points == away_points:
            continue

        if home_points > away_points:
            winner, loser = home_team, away_team
        else:
            winner, loser = away_team, home_team

        # Update winner streak
        if winner not in team_streaks:
            team_streaks[winner] = 'W1'
        else:
            if team_streaks[winner].startswith('W'):
                team_streaks[winner] = f"W{int(team_streaks[winner][1:]) + 1}"
            else:
                team_streaks[winner] = 'W1'

        # Update loser streak
        if loser not in team_streaks:
            team_streaks[loser] = 'L1'
        else:
            if team_streaks[loser].startswith('L'):
                team_streaks[loser] = f"L{int(team_streaks[loser][1:]) + 1}"
            else:
                team_streaks[loser] = 'L1'

    df_standings['Streak'] = df_standings['Team'].map(team_streaks).fillna('N/A')

    # --- Get next game info (future games only) ---
    df_games['startDate'] = pd.to_datetime(df_games['startDate'])
    current_time = pd.to_datetime(datetime.datetime.now(datetime.timezone.utc))
    df_future_games = df_games[df_games['startDate'] > current_time]

    next_game_info = {}
    for team_name in df_standings['Team'].unique():
        team_future_games = df_future_games[
            (df_future_games['homeTeam'] == team_name) | (df_future_games['awayTeam'] == team_name)
        ]
        if not team_future_games.empty:
            earliest_game = team_future_games.sort_values(by='startDate').iloc[0]
            opponent = earliest_game['awayTeam'] if earliest_game['homeTeam'] == team_name else earliest_game['homeTeam']
            next_game_info[team_name] = {'opponent': opponent, 'date': earliest_game['startDate'].strftime('%Y-%m-%d %H:%M')}

    df_standings['Next Game Opponent'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('opponent', 'N/A'))
    df_standings['Next Game Date'] = df_standings['Team'].map(lambda x: next_game_info.get(x, {}).get('date', 'N/A'))

    # --- Merge with picks for drafter performance ---
    df_merged_picks_standings = pd.merge(df_picks, df_standings, left_on='school', right_on='Team', how='left')
    df_drafter_performance = df_merged_picks_standings.groupby('person')['Win Percentage'].mean().reset_index()
    df_leaderboard = df_drafter_performance.sort_values(by='Win Percentage', ascending=False).reset_index(drop=True)

    df_drafter_stats = df_merged_picks_standings.groupby('person')[['Wins', 'Losses']].sum().reset_index()
    df_drafter_stats['Total Games Played'] = df_drafter_stats['Wins'] + df_drafter_stats['Losses']
    df_leaderboard = pd.merge(df_leaderboard, df_drafter_stats, on='person', how='left')

    df_leaderboard = df_leaderboard.drop(columns=['Wins_x', 'Losses_x', 'Total Games Played_x'], errors='ignore')
    df_leaderboard.rename(
        columns={'Wins_y': 'Wins', 'Losses_y': 'Losses', 'Total Games Played_y': 'Total Games Played'},
        inplace=True
    )

    new_column_order = ['person', 'Wins', 'Losses', 'Total Games Played', 'Win Percentage']
    df_leaderboard = df_leaderboard[new_column_order]

    # --- Create team_games_df (team-level game log) ---
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
    team_games_df = team_games_df[
        ['id', 'season', 'startDate', 'team_id', 'opponent_id', 'is_home', 'points_scored', 'points_allowed']
    ].rename(columns={'id': 'game_id', 'startDate': 'game_date'})

    team_games_df['points_scored'] = team_games_df['points_scored'].astype(int)
    team_games_df['points_allowed'] = team_games_df['points_allowed'].astype(int)
    team_games_df['season'] = team_games_df['season'].astype(int)
    team_games_df['game_date'] = pd.to_datetime(team_games_df['game_date'])
    team_games_df['win'] = team_games_df['points_scored'] > team_games_df['points_allowed']
    team_games_df['point_diff'] = team_games_df['points_scored'] - team_games_df['points_allowed']

    # Merge team info
    team_games_df = pd.merge(
        team_games_df,
        df_teams[['id', 'school', 'mascot', 'abbreviation', 'conference']],
        left_on='team_id', right_on='id', how='left'
    ).rename(
        columns={
            'school': 'team_name', 'mascot': 'team_mascot',
            'abbreviation': 'team_abbreviation', 'conference': 'team_conference'
        }
    ).drop(columns=['id'])

    # Merge opponent info
    team_games_df = pd.merge(
        team_games_df,
        df_teams[['id', 'school', 'mascot', 'abbreviation', 'conference']],
        left_on='opponent_id', right_on='id', how='left'
    ).rename(
        columns={
            'school': 'opponent_name', 'mascot': 'opponent_mascot',
            'abbreviation': 'opponent_abbreviation', 'conference': 'opponent_conference'
        }
    ).drop(columns=['id'])

    # --- Merge rankings into team_games_df ---
    team_games_df['game_date'] = pd.to_datetime(team_games_df['game_date'])
    df_rankings['pollDate'] = pd.to_datetime(df_rankings['pollDate'])

    team_games_df_sorted = team_games_df.sort_values(by=['game_date', 'team_id']).reset_index(drop=True)
    df_rankings_sorted = df_rankings.sort_values(by=['pollDate', 'teamId']).reset_index(drop=True)

    df_merged_rankings = pd.merge_asof(
        team_games_df_sorted,
        df_rankings_sorted[['pollDate', 'teamId', 'ranking', 'week']],
        left_on='game_date', right_on='pollDate',
        left_by='team_id', right_by='teamId',
        direction='backward', allow_exact_matches=True
    ).rename(columns={'ranking': 'team_ranking', 'week': 'ranking_week', 'pollDate': 'ranking_pollDate'})

    df_merged_rankings = pd.merge_asof(
        df_merged_rankings,
        df_rankings_sorted[['pollDate', 'teamId', 'ranking', 'week']],
        left_on='game_date', right_on='pollDate',
        left_by='opponent_id', right_by='teamId',
        direction='backward', allow_exact_matches=True, suffixes=('_team', '_opponent')
    ).rename(columns={'ranking_opponent': 'opponent_ranking', 'week_opponent': 'opponent_ranking_week', 'pollDate_opponent': 'opponent_ranking_pollDate'})

    # --- Create a mapping of latest AP Poll ranking for each team ---
    latest_rankings = df_rankings.sort_values('pollDate').drop_duplicates('teamId', keep='last')
    team_rank_map = dict(zip(latest_rankings['teamId'], latest_rankings['ranking']))
    
    # Add team_id to df_merged_picks_standings
    df_merged_picks_standings = pd.merge(
        df_merged_picks_standings,
        df_teams[['school', 'id']],
        left_on='school',
        right_on='school',
        how='left'
    )
    
    # Map the latest ranking
    df_merged_picks_standings['Ranking'] = df_merged_picks_standings['id'].map(team_rank_map)
    df_merged_picks_standings['school_with_rank'] = df_merged_picks_standings.apply(
        lambda row: f"{row['school']} ({row['Ranking']})" if pd.notna(row['Ranking']) else row['school'],
        axis=1
    )
    
    return df_leaderboard, df_merged_picks_standings, df_merged_rankings


# --- Main Streamlit App Logic ---
st.title('Metro Sharon CBB Draft Leaderboard')

# Load and process data
df_picks = load_draft_picks()
df_teams, df_rankings, df_games = fetch_cbbd_data()
df_leaderboard, df_merged_picks_standings, df_merged_rankings = process_data(df_picks, df_teams, df_rankings, df_games)

# --- Display latest game date safely ---
if df_games is not None and isinstance(df_games, pd.DataFrame) and 'startDate' in df_games.columns and not df_games.empty:
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

# Display last updated in Central Time
central_time = datetime.datetime.now(ZoneInfo("America/Chicago"))
st.caption(f"Last updated: {central_time.strftime('%Y-%m-%d %H:%M %Z')}")

# Sort the data by 'Win Percentage' in descending order
leaderboard_data = df_leaderboard.sort_values(by='Win Percentage', ascending=False).reset_index(drop=True)

# Multi-select filter for 'person'
selected_persons = st.multiselect(
    'Filter by Person',
    options=leaderboard_data['person'].unique(),
    default=leaderboard_data['person'].unique()
)

# Filter the dataframe based on selected persons
filtered_leaderboard = leaderboard_data[leaderboard_data['person'].isin(selected_persons)]
filtered_leaderboard['Win Percentage'] = (filtered_leaderboard['Win Percentage'] * 100).round(2)
filtered_leaderboard['Win Percentage'] = filtered_leaderboard['Win Percentage'].apply(lambda x: f"{x:.2f}%")

# Display the filtered and sorted leaderboard
st.subheader('Overall Leaderboard')
st.dataframe(filtered_leaderboard)

# Display individual drafter details
st.subheader('Individual Performance')
for person_name in df_leaderboard['person'].unique():
    with st.expander(f"{person_name}'s Teams"):
       person_teams_df = df_merged_picks_standings[
        df_merged_picks_standings['person'] == person_name
    ][['school_with_rank', 'Wins', 'Losses', 'Streak', 'Win Percentage']].sort_values(by='Win Percentage', ascending=False)

    # Rename column for display
    person_teams_df = person_teams_df.rename(columns={'school_with_rank': 'school'})


        avg_win_pct = person_teams_df['Win Percentage'].mean() if not person_teams_df.empty else 0.0
        avg_win_pct = round(avg_win_pct * 100, 2)

        summary_row = pd.DataFrame([{
            'school': 'Total',
            'Wins': person_teams_df['Wins'].sum(),
            'Losses': person_teams_df['Losses'].sum(),
            'Streak': '',
            'Win Percentage': avg_win_pct
        }])

        person_teams_df['Win Percentage'] = person_teams_df['Win Percentage'].apply(lambda x: f"{x*100:.2f}%")
        summary_row['Win Percentage'] = f"{avg_win_pct:.2f}%"

        final_df = pd.concat([person_teams_df, summary_row], ignore_index=True)
        st.dataframe(final_df)
