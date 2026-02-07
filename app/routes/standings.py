from datetime import datetime
from collections import defaultdict
from flask import Blueprint, render_template, request
from flask_login import login_required
from app import db
from app.models import User, Game, Pick, WeekResult
from app.services.scoring import calculate_pick_points, determine_weekly_prize_winner, determine_yearly_prize_winner, calculate_prizes

standings_bp = Blueprint('standings', __name__)


def _get_current_season():
    now = datetime.now()
    return now.year - 1 if now.month < 3 else now.year


@standings_bp.route('/weekly')
@login_required
def weekly():
    season = request.args.get('season', _get_current_season(), type=int)
    week = request.args.get('week', 1, type=int)
    available_weeks = [w[0] for w in db.session.query(Game.week).filter_by(season=season).distinct().order_by(Game.week).all()]
    results = WeekResult.query.filter_by(season=season, week=week).order_by(WeekResult.total_points.desc()).all()
    user_map = {}
    if results:
        users = User.query.filter(User.id.in_([r.user_id for r in results])).all()
        user_map = {u.id: u for u in users}
    games = Game.query.filter_by(season=season, week=week).order_by(Game.game_time).all()
    game_ids = [g.id for g in games]
    game_map = {g.id: g for g in games}
    all_picks = Pick.query.filter(Pick.game_id.in_(game_ids)).all() if game_ids else []
    user_pick_details = defaultdict(list)
    for pick in all_picks:
        game = game_map.get(pick.game_id)
        if game and game.is_final:
            user_pick_details[pick.user_id].append({'game': game, 'picked_team': pick.picked_team, 'points': calculate_pick_points(game, pick.picked_team)})
    return render_template('standings/weekly.html', results=results, user_map=user_map, user_pick_details=dict(user_pick_details), games=games, season=season, week=week, available_weeks=available_weeks)


@standings_bp.route('/yearly')
@login_required
def yearly():
    season = request.args.get('season', _get_current_season(), type=int)
    all_results = WeekResult.query.filter_by(season=season).all()
    user_season = defaultdict(lambda: {'total_points': 0.0, 'total_weekly_wins': 0.0, 'total_winning_picks': 0, 'weeks_played': 0})
    for r in all_results:
        d = user_season[r.user_id]
        d['total_points'] += r.total_points
        d['total_weekly_wins'] += r.weekly_wins
        d['total_winning_picks'] += r.winning_picks_count
        d['weeks_played'] += 1
    sorted_standings = sorted(user_season.items(), key=lambda x: (x[1]['total_points'], x[1]['total_winning_picks']), reverse=True)
    user_ids = [uid for uid, _ in sorted_standings]
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}
    yearly_winners = determine_yearly_prize_winner(season)
    weekly_winners = determine_weekly_prize_winner(season)
    yearly_winner_ids = {uid for uid, _ in yearly_winners}
    weekly_winner_ids = {uid for uid, _ in weekly_winners}
    prizes = None
    try:
        prizes = calculate_prizes(season)
    except Exception:
        pass
    return render_template('standings/yearly.html', standings=sorted_standings, user_map=user_map, yearly_winner_ids=yearly_winner_ids, weekly_winner_ids=weekly_winner_ids, prizes=prizes, season=season)
