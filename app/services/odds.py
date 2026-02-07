"""Service to fetch NFL spreads from The Odds API."""

import requests
from datetime import datetime, timezone
from flask import current_app


TEAM_NAME_MAP = {
    'Arizona Cardinals': 'Cardinals',
    'Atlanta Falcons': 'Falcons',
    'Baltimore Ravens': 'Ravens',
    'Buffalo Bills': 'Bills',
    'Carolina Panthers': 'Panthers',
    'Chicago Bears': 'Bears',
    'Cincinnati Bengals': 'Bengals',
    'Cleveland Browns': 'Browns',
    'Dallas Cowboys': 'Cowboys',
    'Denver Broncos': 'Broncos',
    'Detroit Lions': 'Lions',
    'Green Bay Packers': 'Packers',
    'Houston Texans': 'Texans',
    'Indianapolis Colts': 'Colts',
    'Jacksonville Jaguars': 'Jaguars',
    'Kansas City Chiefs': 'Chiefs',
    'Las Vegas Raiders': 'Raiders',
    'Los Angeles Chargers': 'Chargers',
    'Los Angeles Rams': 'Rams',
    'Miami Dolphins': 'Dolphins',
    'Minnesota Vikings': 'Vikings',
    'New England Patriots': 'Patriots',
    'New Orleans Saints': 'Saints',
    'New York Giants': 'Giants',
    'New York Jets': 'Jets',
    'Philadelphia Eagles': 'Eagles',
    'Pittsburgh Steelers': 'Steelers',
    'San Francisco 49ers': '49ers',
    'Seattle Seahawks': 'Seahawks',
    'Tampa Bay Buccaneers': 'Buccaneers',
    'Tennessee Titans': 'Titans',
    'Washington Commanders': 'Commanders',
}


def get_short_name(full_name):
    return TEAM_NAME_MAP.get(full_name, full_name)


def fetch_odds():
    """
    Fetch current NFL odds from The Odds API.
    Returns list of dicts: api_id, home_team, away_team, spread, game_time.
    """
    api_key = current_app.config.get('ODDS_API_KEY', '')
    if not api_key:
        raise ValueError(
            'ODDS_API_KEY not configured. Set the ODDS_API_KEY environment variable '
            'or update config.py. Get a free key at https://the-odds-api.com'
        )

    url = current_app.config['ODDS_API_URL']
    params = {
        'apiKey': api_key,
        'regions': 'us',
        'markets': 'spreads',
        'oddsFormat': 'american',
    }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    games = []

    for event in data:
        api_id = event.get('id')
        home_team_full = event.get('home_team', '')
        away_team_full = event.get('away_team', '')
        commence = event.get('commence_time', '')

        home_team = get_short_name(home_team_full)
        away_team = get_short_name(away_team_full)

        try:
            game_time = datetime.fromisoformat(commence.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            game_time = datetime.now(timezone.utc)

        spread = _extract_spread(event, home_team_full)

        games.append({
            'api_id': api_id,
            'home_team': home_team,
            'away_team': away_team,
            'spread': spread,
            'game_time': game_time,
        })

    return games


def _extract_spread(event, home_team_full):
    """Extract point spread for home team. Positive = home favored."""
    bookmakers = event.get('bookmakers', [])
    for bm in bookmakers:
        for market in bm.get('markets', []):
            if market.get('key') == 'spreads':
                outcomes = market.get('outcomes', [])
                for outcome in outcomes:
                    if outcome.get('name') == home_team_full:
                        return -outcome.get('point', 0)
                if outcomes:
                    first = outcomes[0]
                    if first.get('name') == home_team_full:
                        return -first.get('point', 0)
                    else:
                        return first.get('point', 0)
    return 0.0


def determine_nfl_week(game_time, season):
    """Determine NFL week number from game date (approximate)."""
    sept_1 = datetime(season, 9, 1)
    days_until_monday = (7 - sept_1.weekday()) % 7
    if sept_1.weekday() == 0:
        labor_day = sept_1
    else:
        labor_day = sept_1.replace(day=1 + days_until_monday)

    week1_start = labor_day.replace(day=labor_day.day + 1)

    if hasattr(game_time, 'date'):
        game_date = game_time.date()
    else:
        game_date = game_time

    if hasattr(week1_start, 'date'):
        w1 = week1_start.date()
    else:
        w1 = week1_start

    delta = (game_date - w1).days
    week = (delta // 7) + 1
    return max(1, min(18, week))
