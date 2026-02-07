import requests
from datetime import datetime, timezone
from flask import current_app
from app import db
from app.models import Game

TEAM_ABBREVIATIONS = {
    'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LAR', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
    'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS',
}

ESPN_TEAM_MAP = {
    'ARI': 'ARI', 'ATL': 'ATL', 'BAL': 'BAL', 'BUF': 'BUF', 'CAR': 'CAR',
    'CHI': 'CHI', 'CIN': 'CIN', 'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN',
    'DET': 'DET', 'GB': 'GB', 'HOU': 'HOU', 'IND': 'IND', 'JAX': 'JAX',
    'KC': 'KC', 'LV': 'LV', 'LAC': 'LAC', 'LAR': 'LAR', 'LA': 'LAR',
    'MIA': 'MIA', 'MIN': 'MIN', 'NE': 'NE', 'NO': 'NO', 'NYG': 'NYG',
    'NYJ': 'NYJ', 'PHI': 'PHI', 'PIT': 'PIT', 'SF': 'SF', 'SEA': 'SEA',
    'TB': 'TB', 'TEN': 'TEN', 'WSH': 'WAS', 'WAS': 'WAS',
}


def get_team_abbr(full_name):
    return TEAM_ABBREVIATIONS.get(full_name, full_name)


def fetch_odds_from_odds_api():
    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key:
        raise ValueError(
            "No ODDS_API_KEY configured. Get a free key at https://the-odds-api.com"
        )
    url = current_app.config['ODDS_API_URL']
    params = {'apiKey': api_key, 'regions': 'us', 'markets': 'spreads', 'oddsFormat': 'american'}
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response.json()


def fetch_games_from_espn(week_number, season_year):
    url = current_app.config['ESPN_ODDS_URL']
    params = {'week': week_number, 'seasontype': 2, 'dates': season_year}
    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    games = []
    for event in data.get('events', []):
        competition = event.get('competitions', [{}])[0]
        competitors = competition.get('competitors', [])
        if len(competitors) != 2:
            continue

        home = away = None
        for comp in competitors:
            td = {
                'abbr': comp.get('team', {}).get('abbreviation', ''),
                'score': comp.get('score'),
            }
            if comp.get('homeAway') == 'home':
                home = td
            else:
                away = td

        if home and away:
            game_time = None
            gts = event.get('date', '')
            if gts:
                try:
                    game_time = datetime.fromisoformat(gts.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass

            spread = None
            favorite = None
            odds = competition.get('odds', [])
            if odds:
                sv = odds[0].get('spread') if odds[0] else None
                if sv is not None:
                    try:
                        spread = abs(float(sv))
                        favorite = 'home' if float(sv) < 0 else 'away'
                    except (ValueError, TypeError):
                        pass

            ha = ESPN_TEAM_MAP.get(home['abbr'], home['abbr'])
            aa = ESPN_TEAM_MAP.get(away['abbr'], away['abbr'])
            games.append({
                'home_team': ha, 'away_team': aa, 'game_time': game_time,
                'spread': spread, 'favorite': favorite,
                'espn_id': event.get('id'),
                'home_score': int(home['score']) if home.get('score') else None,
                'away_score': int(away['score']) if away.get('score') else None,
                'status': event.get('status', {}).get('type', {}).get('name', ''),
            })
    return games


def fetch_odds_for_week(week):
    season_year = week.season.year
    week_number = week.week_number
    espn_games = fetch_games_from_espn(week_number, season_year)

    odds_map = {}
    try:
        odds_data = fetch_odds_from_odds_api()
        for event in odds_data:
            ht = get_team_abbr(event.get('home_team', ''))
            at = get_team_abbr(event.get('away_team', ''))
            for bm in event.get('bookmakers', []):
                for market in bm.get('markets', []):
                    if market.get('key') == 'spreads':
                        for outcome in market.get('outcomes', []):
                            team = get_team_abbr(outcome.get('name', ''))
                            point = outcome.get('point')
                            if team == ht and point is not None:
                                odds_map[f"{at}@{ht}"] = {
                                    'spread': abs(float(point)),
                                    'favorite': 'home' if float(point) < 0 else 'away'
                                }
                                break
                        break
                break
    except Exception:
        pass

    count = 0
    for gd in espn_games:
        existing = Game.query.filter_by(
            week_id=week.id, home_team=gd['home_team'], away_team=gd['away_team']
        ).first()

        key = f"{gd['away_team']}@{gd['home_team']}"
        if key in odds_map:
            gd['spread'] = odds_map[key]['spread']
            gd['favorite'] = odds_map[key]['favorite']

        if existing:
            if gd.get('spread') is not None:
                existing.spread = gd['spread']
                existing.favorite = gd['favorite']
            if gd.get('game_time'):
                existing.game_time = gd['game_time']
            if gd.get('home_score') is not None:
                existing.home_score = gd['home_score']
                existing.away_score = gd['away_score']
            if gd.get('status') == 'STATUS_FINAL':
                existing.is_final = True
            existing.espn_id = gd.get('espn_id')
        else:
            game = Game(
                week_id=week.id, home_team=gd['home_team'], away_team=gd['away_team'],
                spread=gd.get('spread'), favorite=gd.get('favorite'),
                game_time=gd.get('game_time'), espn_id=gd.get('espn_id'),
            )
            if gd.get('status') == 'STATUS_FINAL':
                game.is_final = True
                game.home_score = gd.get('home_score')
                game.away_score = gd.get('away_score')
            db.session.add(game)
        count += 1

    db.session.commit()
    return count
