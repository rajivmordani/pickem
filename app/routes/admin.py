from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Game, Pick, WeekResult



admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('picks.weekly'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@admin_required
def users():
    return render_template('admin/users.html', users=User.query.order_by(User.display_name).all())


@admin_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username', '').strip().lower()
    email = request.form.get('email', '').strip().lower()
    display_name = request.form.get('display_name', '').strip()
    password = request.form.get('password', '').strip()
    is_admin = request.form.get('is_admin') == 'on'
    if not all([username, email, display_name, password]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin.users'))
    user = User(username=username, email=email, display_name=display_name, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{display_name}" created!', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot deactivate yourself.', 'danger')
    else:
        user.is_active_player = not user.is_active_player
        db.session.commit()
        flash(f'User toggled.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    pw = request.form.get('new_password', '').strip()
    if len(pw) < 6:
        flash('Password must be 6+ chars.', 'danger')
    else:
        user.set_password(pw)
        db.session.commit()
        flash('Password reset.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/seasons')
@admin_required
def seasons():
    return render_template('admin/seasons.html', seasons=Season.query.order_by(Season.year.desc()).all())


@admin_bp.route('/seasons/create', methods=['POST'])
@admin_required
def create_season():
    year = request.form.get('year', type=int)
    total_weeks = request.form.get('total_weeks', 18, type=int)
    if not year:
        flash('Year required.', 'danger')
        return redirect(url_for('admin.seasons'))
    if Season.query.filter_by(year=year).first():
        flash('Season exists.', 'danger')
        return redirect(url_for('admin.seasons'))
    Season.query.update({Season.is_active: False})
    season = Season(year=year, is_active=True, total_weeks=total_weeks)
    db.session.add(season)
    db.session.flush()
    for wn in range(1, total_weeks + 1):
        db.session.add(Week(season_id=season.id, week_number=wn))
    db.session.commit()
    flash(f'Season {year} created.', 'success')
    return redirect(url_for('admin.seasons'))


@admin_bp.route('/weeks/<int:week_id>')
@admin_required
def manage_week(week_id):
    week = Week.query.get_or_404(week_id)
    games = Game.query.filter_by(week_id=week_id).order_by(Game.game_time).all()
    return render_template('admin/manage_week.html', week=week, games=games)


@admin_bp.route('/weeks/<int:week_id>/toggle-open', methods=['POST'])
@admin_required
def toggle_week_open(week_id):
    week = Week.query.get_or_404(week_id)
    week.is_open_for_picks = not week.is_open_for_picks
    db.session.commit()
    flash(f'Week {week.week_number} toggled.', 'success')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/fetch-odds', methods=['POST'])
@admin_required
def fetch_week_odds(week_id):
    week = Week.query.get_or_404(week_id)
    try:
        count = fetch_odds_for_week(week)
        flash(f'Fetched {count} games.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/add-game', methods=['POST'])
@admin_required
def add_game(week_id):
    home = request.form.get('home_team', '').strip()
    away = request.form.get('away_team', '').strip()
    spread = request.form.get('spread', type=float)
    fav = request.form.get('favorite', 'home')
    gts = request.form.get('game_time', '').strip()
    if not all([home, away]):
        flash('Teams required.', 'danger')
        return redirect(url_for('admin.manage_week', week_id=week_id))
    gt = None
    if gts:
        try:
            gt = datetime.fromisoformat(gts).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    db.session.add(Game(week_id=week_id, home_team=home, away_team=away, spread=spread, favorite=fav, game_time=gt))
    db.session.commit()
    flash(f'{away} @ {home} added.', 'success')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/games/<int:game_id>/update', methods=['POST'])
@admin_required
def update_game(game_id):
    game = Game.query.get_or_404(game_id)
    s = request.form.get('spread', type=float)
    f = request.form.get('favorite')
    hs = request.form.get('home_score', type=int)
    aws = request.form.get('away_score', type=int)
    final = request.form.get('is_final') == 'on'
    gts = request.form.get('game_time', '').strip()
    if s is not None: game.spread = s
    if f: game.favorite = f
    if gts:
        try: game.game_time = datetime.fromisoformat(gts).replace(tzinfo=timezone.utc)
        except ValueError: pass
    game.home_score = hs
    game.away_score = aws
    game.is_final = final
    if final and hs is not None and aws is not None:
        for pick in Pick.query.filter_by(game_id=game_id).all():
            pick.points = game.calculate_points(pick.picked_team)
    db.session.commit()
    flash('Game updated.', 'success')
    return redirect(url_for('admin.manage_week', week_id=game.week_id))


@admin_bp.route('/games/<int:game_id>/delete', methods=['POST'])
@admin_required
def delete_game(game_id):
    game = Game.query.get_or_404(game_id)
    wid = game.week_id
    Pick.query.filter_by(game_id=game_id).delete()
    db.session.delete(game)
    db.session.commit()
    flash('Game deleted.', 'success')
    return redirect(url_for('admin.manage_week', week_id=wid))


@admin_bp.route('/weeks/<int:week_id>/calculate', methods=['POST'])
@admin_required
def calculate_results(week_id):
    week = Week.query.get_or_404(week_id)
    try:
        calculate_week_results(week)
        flash('Results calculated.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/complete', methods=['POST'])
@admin_required
def complete_week(week_id):
    week = Week.query.get_or_404(week_id)
    if Game.query.filter_by(week_id=week_id, is_final=False).count() > 0:
        flash('Not all games final.', 'danger')
        return redirect(url_for('admin.manage_week', week_id=week_id))
    calculate_week_results(week)
    week.is_completed = True
    week.is_open_for_picks = False
    db.session.commit()
    flash(f'Week {week.week_number} completed.', 'success')
    return redirect(url_for('admin.manage_week', week_id=week_id))
