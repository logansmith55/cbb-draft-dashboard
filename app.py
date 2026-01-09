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

# --- Fetch games ---
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
    df_games['startDate'] = pd.to_datetime(df_games['startDate'])
    return df_games

# --- Daily Scoreboard Helper ---
def generate_daily_scoreboard(df_games, df_picks, selected_date, selected_persons=None):
    draft_teams = df_picks[['school','person']]

    # Filter by date
    mask = df_games['startDate'].dt.date == selected_date
    df_daily = df_games[mask]

    if df_daily.empty:
        st.write(f"No games for drafted teams on {selected_date}.")
        return

    # Merge owner info
    df_daily = df_daily.merge(draft_teams.rename(columns={'school':'homeTeam','person':'homePerson'}),
                              left_on='homeTeam', right_on='homeTeam', how='left')
    df_daily = df_daily.merge(draft_teams.rename(columns={'school':'awayTeam','person':'awayPerson'}),
                              left_on='awayTeam', right_on='awayTeam', how='left')

    # Filter by selected person(s) if given
    if selected_persons:
        df_daily = df_daily[(df_daily['homePerson'].isin(selected_persons)) | (df_daily['awayPerson'].isin(selected_persons))]

    # Big games: both teams have owners
    big_games = df_daily.dropna(subset=['homePerson','awayPerson'])
    normal_games = df_daily[~df_daily.index.isin(big_games.index)]

    def format_table(df):
        rows = []
        for _, row in df.iterrows():
            home_owner = row['homePerson'] if pd.notna(row['homePerson']) else "N/A"
            away_owner = row['awayPerson'] if pd.notna(row['awayPerson']) else "N/A"
            home_score = row['homePoints'] if pd.notna(row['homePoints']) else ""
            away_score = row['awayPoints'] if pd.notna(row['awayPoints']) else ""
            time_str = row['startDate'].strftime("%I:%M %p")

            # Highlight winner by bold text
            if home_score != "" and away_score != "":
                if home_score > away_score:
                    home_team = f"**{row['homeTeam']} ({home_owner})**"
                    away_team = f"{row['awayTeam']} ({away_owner})"
                elif away_score > home_score:
                    home_team = f"{row['homeTeam']} ({home_owner})"
                    away_team = f"**{row['awayTeam']} ({away_owner})**"
                else:
                    home_team = f"{row['homeTeam']} ({home_owner})"
                    away_team = f"{row['awayTeam']} ({away_owner})"
            else:
                home_team = f"{row['homeTeam']} ({home_owner})"
                away_team = f"{row['awayTeam']} ({away_owner})"

            rows.append({
                "Time": time_str,
                "Home Team": home_team,
                "Home Score": home_score,
                "Away Team": away_team,
                "Away Score": away_score
            })
        return pd.DataFrame(rows)

    st.subheader(f"Big Games ({selected_date})")
    if not big_games.empty:
        st.table(format_table(big_games))
    else:
        st.write("No big games today.")

    # Display normal games by person
    for person in sorted(df_picks['person'].unique()):
        if selected_persons and person not in selected_persons:
            continue
        person_games = normal_games[(normal_games['homePerson']==person) | (normal_games['awayPerson']==person)]
        if person_games.empty:
            continue
        st.subheader(f"{person}'s Teams ({selected_date})")
        st.table(format_table(person_games))

# --- Main App ---
st.title("Metro Sharon CBB Draft Dashboard")
tab1, tab2 = st.tabs(["Leaderboard", "Daily Scoreboard"])

st.title("Metro Sharon CBB Draft Dashboard")
tab1, tab2 = st.tabs(["Leaderboard", "Daily Scoreboard"])

# --- TAB 1: Leaderboard ---
with tab1:
    # Your **existing leaderboard code** goes here.
    # For example:
    df_picks = load_draft_picks()
    df_teams = fetch_teams()
    df_rankings = fetch_rankings()
    df_games = fetch_games()
    df_leaderboard, df_merged = process_data(df_picks, df_teams, df_rankings, df_games)

    st.caption(f"Last updated: {datetime.datetime.now(ZoneInfo('America/Chicago')).strftime('%Y-%m-%d %H:%M %Z')}")

    leaderboard_data = df_leaderboard.sort_values('Win Percentage', ascending=False).reset_index(drop=True)
    leaderboard_data['Win Percentage'] = leaderboard_data['Win Percentage'].apply(lambda x: f"{x*100:.2f}%")
    st.subheader("Overall Leaderboard")
    st.dataframe(leaderboard_data)

    # Individual performance
    st.subheader("Individual Performance")
    for person in df_leaderboard['person'].unique():
        with st.expander(f"{person}'s Teams"):
            person_df = df_merged[df_merged['person']==person][
                ['school_with_rank','Wins','Losses','Streak','Win Percentage']
            ].sort_values('Win Percentage', ascending=False)
            person_df = person_df.rename(columns={'school_with_rank':'school'})
            avg_win_pct = person_df['Win Percentage'].mean() if not person_df.empty else 0
            avg_win_pct = round(avg_win_pct*100,2)
            person_df['Win Percentage'] = person_df['Win Percentage'].apply(lambda x: f"{x*100:.2f}%")
            summary = pd.DataFrame([{
                'school':'Total',
                'Wins': person_df['Wins'].sum(),
                'Losses': person_df['Losses'].sum(),
                'Streak':'',
                'Win Percentage': f"{avg_win_pct:.2f}%"
            }])
            st.dataframe(pd.concat([person_df, summary], ignore_index=True))

# --- TAB 2: Daily Scoreboard ---
with tab2:
    st.subheader("Daily Scoreboard")
    today = datetime.datetime.now(ZoneInfo("America/Chicago")).date()
    selected_date = st.date_input("Select Date", value=today)

    df_picks = load_draft_picks()
    df_games = fetch_games()

    # Person filter
    persons = sorted(df_picks['person'].unique())
    selected_persons = st.multiselect("Filter by Person", options=persons, default=persons)

    generate_daily_scoreboard(df_games, df_picks, selected_date, selected_persons)
