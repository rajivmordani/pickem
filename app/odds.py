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


def get_team_abbr(name):
    return TEAM_ABBREVIATIONS.get(name, name)


def fetch_odds_from_odds_api():
    key = current_app.config.get('ODDS_API_KEY', '')
    if not key:
        raise ValueError("No ODDS_API_KEY. Get one at https://the-odds-api.com")
    r = requests.get(current_app.config['ODDS_API_URL'],
                     params={'apiKey': key, 'regions': 'us', 'markets': 'spreads', 'oddsFormat': 'american'},
                     timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_games_from_espn(week_number, season_year):
    r = requests.get(current_app.config['ESPN_ODDS_URL'],
                     params={'week': week_number, 'seasontype': 2, 'dates': season_year}, timeout=15)
    r.raise_for_status()
    data = r.json()
    games = []
    for ev in data.get('events', []):
        comp = ev.get('competitions', [{}])[0]
        cs = comp.get('competitors', [])
        if len(cs) != 2: continue
        home = away = None
        for c in cs:
            td = {'abbr': c.get('team', {}).get('abbreviation', ''), 'score': c.get('score')}
            if c.get('homeAway') == 'home': home = td
            else: away = td
        if not (home and away): continue
        gt = None
        gts = ev.get('date', '')
        if gts:
            try: gt = datetime.fromisoformat(gts.replace('Z', '+00:00'))
            except: pass
        spread = fav = None
        odds = comp.get('odds', [])
        if odds and odds[0]:
            sv = odds[0].get('spread')
            if sv is not None:
                try:
                    spread = abs(float(sv))
                    fav = 'home' if float(sv) < 0 else 'away'
                except: pass
        games.append({
            'home_team': ESPN_TEAM_MAP.get(home['abbr'], home['abbr']),
            'away_team': ESPN_TEAM_MAP.get(away['abbr'], away['abbr']),
            'game_time': gt, 'spread': spread, 'favorite': fav,
            'espn_id': ev.get('id'),
            'home_score': int(home['score']) if home.get('score') else None,
            'away_score': int(away['score']) if away.get('score') else None,
            'status': ev.get('status', {}).get('type', {}).get('name', ''),
        })
    return games


def fetch_odds_for_week(week):
    espn_games = fetch_games_from_espn(week.week_number, week.season.year)
    odds_map = {}
    try:
        for ev in fetch_odds_from_odds_api():
            ht = get_team_abbr(ev.get('home_team', ''))
            at = get_team_abbr(ev.get('away_team', ''))
            for bm in ev.get('bookmakers', []):
                for m in bm.get('markets', []):
                    if m.get('key') == 'spreads':
                        for o in m.get('outcomes', []):
                            t = get_team_abbr(o.get('name', ''))
                            pt = o.get('point')
                            if t == ht and pt is not None:
                                odds_map[f"{at}@{ht}"] = {'spread': abs(float(pt)), 'favorite': 'home' if float(pt) < 0 else 'away'}
                                break
                        break
                break
    except: pass
    count = 0
    for gd in espn_games:
        key = f"{gd['away_team']}@{gd['home_team']}"
        if key in odds_map:
            gd['spread'] = odds_map[key]['spread']
            gd['favorite'] = odds_map[key]['favorite']
        ex = Game.query.filter_by(week_id=week.id, home_team=gd['home_team'], away_team=gd['away_team']).first()
        if ex:
            if gd.get('spread') is not None: ex.spread = gd['spread']; ex.favorite = gd['favorite']
            if gd.get('game_time'): ex.game_time = gd['game_time']
            if gd.get('home_score') is not None: ex.home_score = gd['home_score']; ex.away_score = gd['away_score']
            if gd.get('status') == 'STATUS_FINAL': ex.is_final = True
            ex.espn_id = gd.get('espn_id')
        else:
            g = Game(week_id=week.id, home_team=gd['home_team'], away_team=gd['away_team'],
                     spread=gd.get('spread'), favorite=gd.get('favorite'),
                     game_time=gd.get('game_time'), espn_id=gd.get('espn_id'))
            if gd.get('status') == 'STATUS_FINAL':
                g.is_final = True; g.home_score = gd.get('home_score'); g.away_score = gd.get('away_score')
            db.session.add(g)
        count += 1
    db.session.commit()
    return count
