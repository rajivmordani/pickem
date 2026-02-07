from datetime import datetime, timezone
from collections import defaultdict
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Game, Pick
from app.services.scoring import calculate_pick_points

picks_bp = Blueprint('picks', __name__)


def _get_current_season():
    now = datetime.now()
    return now.year - 1 if now.month < 3 else now.year


@picks_bp.route('/')
@login_required
def weekly():
    season = request.args.get('season', _get_current_season(), type=int)
    week = request.args.get('week', None, type=int)
    available_weeks = [w[0] for w in db.session.query(Game.week).filter_by(season=season).distinct().order_by(Game.week).all()]
    if week is None:
        week = available_weeks[-1] if available_weeks else 1
    games = Game.query.filter_by(season=season, week=week).order_by(Game.game_time).all()
    game_ids = [g.id for g in games]
    user_picks = {}
    if game_ids:
        picks = Pick.query.filter(Pick.user_id == current_user.id, Pick.game_id.in_(game_ids)).all()
        user_picks = {p.game_id: p for p in picks}
    has_submitted = len(user_picks) > 0
    all_games_started = all(g.has_started for g in games) if games else False
    can_pick = not all_games_started
    others_picks = {}
    other_users = []
    if has_submitted:
        other_picks_query = Pick.query.filter(Pick.game_id.in_(game_ids), Pick.user_id != current_user.id).all()
        for p in other_picks_query:
            if p.user_id not in others_picks:
                others_picks[p.user_id] = {}
            others_picks[p.user_id][p.game_id] = p
        other_user_ids = list(others_picks.keys())
        if other_user_ids:
            other_users = User.query.filter(User.id.in_(other_user_ids)).all()
    game_points = {}
    for game in games:
        if game.is_final:
            for pick in game.picks:
                game_points[(pick.user_id, game.id)] = calculate_pick_points(game, pick.picked_team)
    return render_template('picks/weekly.html', games=games, user_picks=user_picks, has_submitted=has_submitted, can_pick=can_pick, others_picks=others_picks, other_users=other_users, game_points=game_points, season=season, week=week, available_weeks=available_weeks, current_user_id=current_user.id)


@picks_bp.route('/submit', methods=['POST'])
@login_required
def submit_picks():
    season = request.form.get('season', _get_current_season(), type=int)
    week = request.form.get('week', 1, type=int)
    games = Game.query.filter_by(season=season, week=week).all()
    new_picks = {}
    for game in games:
        picked_team = request.form.get(f'pick_{game.id}')
        if picked_team:
            if game.has_started:
                flash(f'Cannot pick {game.away_team} @ {game.home_team} - game already started.', 'warning')
                continue
            if picked_team not in (game.home_team, game.away_team):
                flash(f'Invalid team for {game.away_team} @ {game.home_team}.', 'danger')
                continue
            new_picks[game.id] = picked_team
    if not new_picks:
        flash('No valid picks submitted.', 'warning')
        return redirect(url_for('picks.weekly', season=season, week=week))
    game_ids = [g.id for g in games if not g.has_started]
    if game_ids:
        Pick.query.filter(Pick.user_id == current_user.id, Pick.game_id.in_(game_ids)).delete(synchronize_session=False)
    for game_id, team in new_picks.items():
        db.session.add(Pick(user_id=current_user.id, game_id=game_id, picked_team=team))
    db.session.commit()
    flash(f'Picks submitted for Week {week}! You made {len(new_picks)} pick(s).', 'success')
    return redirect(url_for('picks.weekly', season=season, week=week))


@picks_bp.route('/history')
@login_required
def history():
    season = request.args.get('season', _get_current_season(), type=int)
    user_picks = Pick.query.join(Game).filter(Pick.user_id == current_user.id, Game.season == season).all()
    weeks_data = defaultdict(lambda: {'picks': [], 'total_points': 0, 'winning_count': 0})
    for pick in user_picks:
        game = pick.game
        pts = calculate_pick_points(game, pick.picked_team) if game.is_final else None
        weeks_data[game.week]['picks'].append({'game': game, 'pick': pick, 'points': pts})
        if pts is not None:
            weeks_data[game.week]['total_points'] += pts
            if pts > 0:
                weeks_data[game.week]['winning_count'] += 1
    weeks_data = dict(sorted(weeks_data.items()))
    return render_template('picks/history.html', weeks_data=weeks_data, season=season)
