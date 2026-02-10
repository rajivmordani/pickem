from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Season, Week, Game, Pick, PickViewLog

picks_bp = Blueprint('picks', __name__)


def _get_active_season():
    return Season.query.filter_by(is_active=True).first()


def _has_viewed_others(user_id, week_id):
    return PickViewLog.query.filter_by(user_id=user_id, week_id=week_id).first() is not None


def _record_view(user_id, week_id):
    if not _has_viewed_others(user_id, week_id):
        db.session.add(PickViewLog(user_id=user_id, week_id=week_id))
        db.session.commit()


@picks_bp.route('/')
@login_required
def picks_index():
    season = _get_active_season()
    if not season:
        flash('No active season. Contact the administrator.', 'warning')
        return redirect(url_for('main.index'))
    week = (
        Week.query.filter_by(season_id=season.id, is_open_for_picks=True)
        .order_by(Week.week_number).first()
    )
    if not week:
        week = Week.query.filter_by(season_id=season.id).order_by(Week.week_number.desc()).first()
    if not week:
        flash('No weeks available.', 'warning')
        return redirect(url_for('main.index'))
    return redirect(url_for('picks.make_picks', week_id=week.id))


@picks_bp.route('/week/<int:week_id>', methods=['GET'])
@login_required
def make_picks(week_id):
    week = db.session.get(Week, week_id)
    if not week:
        flash('Week not found.', 'danger')
        return redirect(url_for('picks.picks_index'))
    games = Game.query.filter_by(week_id=week.id).order_by(Game.game_time).all()
    game_ids = [g.id for g in games]
    user_picks = {}
    if game_ids:
        picks = Pick.query.filter(Pick.user_id == current_user.id, Pick.game_id.in_(game_ids)).all()
        user_picks = {p.game_id: p for p in picks}
    has_submitted = len(user_picks) > 0
    has_viewed = _has_viewed_others(current_user.id, week.id)
    view_others = request.args.get('view_others') == '1'
    show_others = False
    others_picks = {}
    other_users = []
    if has_submitted and (view_others or has_viewed or week.is_completed):
        if not week.is_completed:
            _record_view(current_user.id, week.id)
            has_viewed = True
        show_others = True
        if game_ids:
            other_picks_list = Pick.query.filter(
                Pick.game_id.in_(game_ids), Pick.user_id != current_user.id
            ).all()
            for p in other_picks_list:
                others_picks.setdefault(p.user_id, {})[p.game_id] = p
            if others_picks:
                other_users = User.query.filter(User.id.in_(list(others_picks.keys()))).all()
    can_pick = week.is_open_for_picks and not has_viewed
    can_resubmit = has_submitted and can_pick
    game_points = {}
    for game in games:
        if game.is_final:
            for pick in game.picks:
                pts = game.calculate_points(pick.picked_team)
                if pts is not None:
                    game_points[(pick.user_id, game.id)] = pts
    all_weeks = Week.query.filter_by(season_id=week.season_id).order_by(Week.week_number).all()
    return render_template(
        'picks/weekly.html',
        week=week, games=games, user_picks=user_picks,
        has_submitted=has_submitted, has_viewed=has_viewed,
        show_others=show_others, can_pick=can_pick, can_resubmit=can_resubmit,
        others_picks=others_picks, other_users=other_users,
        game_points=game_points, all_weeks=all_weeks,
        current_user_id=current_user.id,
    )


@picks_bp.route('/week/<int:week_id>/submit', methods=['POST'])
@login_required
def submit_picks(week_id):
    week = db.session.get(Week, week_id)
    if not week:
        flash('Week not found.', 'danger')
        return redirect(url_for('picks.picks_index'))
    if not week.is_open_for_picks:
        flash('Picks are closed for this week.', 'warning')
        return redirect(url_for('picks.make_picks', week_id=week_id))
    if _has_viewed_others(current_user.id, week.id):
        flash("You cannot resubmit picks after viewing others' picks.", 'danger')
        return redirect(url_for('picks.make_picks', week_id=week_id))
    games = Game.query.filter_by(week_id=week.id).all()
    games_by_id = {g.id: g for g in games}
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
        return redirect(url_for('picks.make_picks', week_id=week_id))
    not_started_ids = [g.id for g in games if not g.has_started]
    if not_started_ids:
        Pick.query.filter(
            Pick.user_id == current_user.id, Pick.game_id.in_(not_started_ids)
        ).delete(synchronize_session=False)
    for game_id, team in new_picks.items():
        db.session.add(Pick(user_id=current_user.id, game_id=game_id, picked_team=team))
    db.session.commit()
    
    # Send confirmation email
    try:
        from app.email import send_picks_confirmation
        picks_data = []
        for game_id, team in new_picks.items():
            game = games_by_id.get(game_id)
            if game:
                picks_data.append({
                    'picked_team': team,
                    'away_team': game.away_team,
                    'home_team': game.home_team,
                    'spread_display': game.spread_display,
                })
        send_picks_confirmation(current_user, week, picks_data)
    except Exception as e:
        # Email is optional, don't fail if it doesn't work
        pass
    
    flash(f'Picks submitted for Week {week.week_number}! You made {len(new_picks)} pick(s).', 'success')
    return redirect(url_for('picks.make_picks', week_id=week_id))
