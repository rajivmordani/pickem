from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Season, Week, Game, Pick, User, PickViewLog

picks_bp = Blueprint('picks', __name__)


def user_has_picks(uid, wid):
    gids = [g.id for g in Game.query.filter_by(week_id=wid).all()]
    return bool(gids) and Pick.query.filter(Pick.user_id == uid, Pick.game_id.in_(gids)).count() > 0


def viewed_others(uid, wid):
    return PickViewLog.query.filter_by(user_id=uid, week_id=wid).first() is not None


def record_view(uid, wid):
    if not PickViewLog.query.filter_by(user_id=uid, week_id=wid).first():
        db.session.add(PickViewLog(user_id=uid, week_id=wid))
        db.session.commit()


@picks_bp.route('/')
@login_required
def picks_index():
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        flash('No active season.', 'info')
        return redirect(url_for('picks.weekly'))
    return render_template('picks/index.html', season=season,
                           weeks=Week.query.filter_by(season_id=season.id).order_by(Week.week_number).all())


@picks_bp.route('/week/<int:week_id>')
@login_required
def make_picks(week_id):
    week = Week.query.get_or_404(week_id)
    games = Game.query.filter_by(week_id=week_id).order_by(Game.game_time).all()
    gids = [g.id for g in games]
    user_picks = {}
    if gids:
        user_picks = {p.game_id: p.picked_team for p in
                      Pick.query.filter(Pick.user_id == current_user.id, Pick.game_id.in_(gids)).all()}
    has_submitted = len(user_picks) > 0
    has_viewed = viewed_others(current_user.id, week_id)
    show_others = False
    vr = request.args.get('view_others') == '1'
    if week.is_completed:
        show_others = True
    elif has_submitted and has_viewed:
        show_others = True
    elif has_submitted and vr:
        record_view(current_user.id, week_id)
        has_viewed = True
        show_others = True
    for g in games:
        g.can_pick = week.is_open_for_picks and not g.has_started and (not has_submitted or not has_viewed)
    all_user_picks = {}
    if show_others:
        for u in User.query.filter_by(is_active_player=True).all():
            ps = Pick.query.filter(Pick.user_id == u.id, Pick.game_id.in_(gids)).all()
            if ps:
                all_user_picks[u.display_name] = {p.game_id: p for p in ps}
    return render_template('picks/make_picks.html', week=week, games=games, user_picks=user_picks,
                           has_submitted=has_submitted, show_others=show_others,
                           all_user_picks=all_user_picks,
                           can_resubmit=has_submitted and week.is_open_for_picks and not has_viewed,
                           can_request_view=has_submitted and not has_viewed and not week.is_completed,
                           has_viewed=has_viewed)


@picks_bp.route('/week/<int:week_id>/submit', methods=['POST'])
@login_required
def submit_picks(week_id):
    week = Week.query.get_or_404(week_id)
    if not week.is_open_for_picks:
        flash('Not open.', 'danger')
        return redirect(url_for('picks.make_picks', week_id=week_id))
    if user_has_picks(current_user.id, week_id) and viewed_others(current_user.id, week_id):
        flash("Can't change after viewing others.", 'danger')
        return redirect(url_for('picks.make_picks', week_id=week_id))
    games = Game.query.filter_by(week_id=week_id).all()
    gids = [g.id for g in games]
    if gids:
        Pick.query.filter(Pick.user_id == current_user.id, Pick.game_id.in_(gids)).delete(synchronize_session=False)
    n = 0
    for g in games:
        v = request.form.get(f'pick_{g.id}')
        if v and not g.has_started:
            db.session.add(Pick(user_id=current_user.id, game_id=g.id, picked_team=v))
            n += 1
    db.session.commit()
    if n == 0:
        flash('No picks made.', 'warning')
    elif n < 4:
        flash(f'{n} pick(s). Need 4+ to be eligible.', 'warning')
    else:
        flash(f'{n} pick(s) submitted!', 'success')
    return redirect(url_for('picks.make_picks', week_id=week_id))


@picks_bp.route('/week/<int:week_id>/results')
@login_required
def week_results(week_id):
    week = Week.query.get_or_404(week_id)
    if not week.is_completed and not (user_has_picks(current_user.id, week_id) and viewed_others(current_user.id, week_id)):
        flash('Make picks and view others first!', 'info')
        return redirect(url_for('picks.make_picks', week_id=week_id))
    if user_has_picks(current_user.id, week_id):
        record_view(current_user.id, week_id)
    games = Game.query.filter_by(week_id=week_id).order_by(Game.game_time).all()
    gids = [g.id for g in games]
    user_data = []
    for u in User.query.filter_by(is_active_player=True).order_by(User.display_name).all():
        ps = Pick.query.filter(Pick.user_id == u.id, Pick.game_id.in_(gids)).all()
        if ps:
            user_data.append({
                'user': u, 'picks': {p.game_id: p for p in ps},
                'total_points': sum(p.points or 0 for p in ps),
                'winning_picks': sum(1 for p in ps if p.is_winning_pick),
                'num_picks': len(ps)
            })
    user_data.sort(key=lambda x: (-x['total_points'], -x['winning_picks']))
    from app.models import WeeklyResult
    wrs = WeeklyResult.query.filter_by(week_id=week_id).all()
    winners = {wr.user_id: wr for wr in wrs if wr.weekly_win_share > 0}
    return render_template('picks/week_results.html', week=week, games=games, user_data=user_data, winners=winners)
