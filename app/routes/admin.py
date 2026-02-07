from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Season, Week, Game, Pick, WeeklyResult
from app.scoring import calculate_week_results
from app.odds import fetch_odds_for_week

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Administrator access required.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


# ── User Management ──────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username', '').strip()
    display_name = request.form.get('display_name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    is_admin = bool(request.form.get('is_admin'))

    if not username or not email or not password or not display_name:
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin.users'))
    if User.query.filter_by(email=email).first():
        flash('Email already in use.', 'danger')
        return redirect(url_for('admin.users'))

    user = User(username=username, display_name=display_name, email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{display_name}" created successfully.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    user = db.session.get(User, user_id)
    if user:
        user.is_active_player = not user.is_active_player
        db.session.commit()
        status = 'activated' if user.is_active_player else 'deactivated'
        flash(f'{user.display_name} has been {status}.', 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_password(user_id):
    user = db.session.get(User, user_id)
    if user:
        new_pw = request.form.get('new_password', '')
        if len(new_pw) < 4:
            flash('Password must be at least 4 characters.', 'danger')
        else:
            user.set_password(new_pw)
            db.session.commit()
            flash(f'Password reset for {user.display_name}.', 'success')
    return redirect(url_for('admin.users'))


# ── Season Management ────────────────────────────────────────────────────────

@admin_bp.route('/seasons')
@admin_required
def seasons():
    all_seasons = Season.query.order_by(Season.year.desc()).all()
    return render_template('admin/seasons.html', seasons=all_seasons)


@admin_bp.route('/seasons/create', methods=['POST'])
@admin_required
def create_season():
    year = request.form.get('year', type=int)
    if not year:
        flash('Year is required.', 'danger')
        return redirect(url_for('admin.seasons'))
    if Season.query.filter_by(year=year).first():
        flash(f'Season {year} already exists.', 'danger')
        return redirect(url_for('admin.seasons'))
    # Deactivate other seasons
    Season.query.update({Season.is_active: False})
    season = Season(year=year, is_active=True)
    db.session.add(season)
    db.session.flush()
    # Create 18 weeks
    for wn in range(1, 19):
        db.session.add(Week(season_id=season.id, week_number=wn))
    db.session.commit()
    flash(f'Season {year} created with 18 weeks.', 'success')
    return redirect(url_for('admin.seasons'))


@admin_bp.route('/seasons/<int:season_id>/activate', methods=['POST'])
@admin_required
def activate_season(season_id):
    Season.query.update({Season.is_active: False})
    season = db.session.get(Season, season_id)
    if season:
        season.is_active = True
        db.session.commit()
        flash(f'Season {season.year} activated.', 'success')
    return redirect(url_for('admin.seasons'))


# ── Week / Game Management ───────────────────────────────────────────────────

@admin_bp.route('/weeks/<int:week_id>')
@admin_required
def manage_week(week_id):
    week = db.session.get(Week, week_id)
    if not week:
        flash('Week not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    games = Game.query.filter_by(week_id=week.id).order_by(Game.game_time).all()
    return render_template('admin/manage_week.html', week=week, games=games)


@admin_bp.route('/weeks/<int:week_id>/toggle-picks', methods=['POST'])
@admin_required
def toggle_picks(week_id):
    week = db.session.get(Week, week_id)
    if week:
        week.is_open_for_picks = not week.is_open_for_picks
        db.session.commit()
        status = 'opened' if week.is_open_for_picks else 'closed'
        flash(f'Picks {status} for Week {week.week_number}.', 'info')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/fetch-odds', methods=['POST'])
@admin_required
def fetch_odds(week_id):
    week = db.session.get(Week, week_id)
    if not week:
        flash('Week not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    try:
        count = fetch_odds_for_week(week)
        flash(f'Fetched/updated {count} games for Week {week.week_number}.', 'success')
    except Exception as e:
        flash(f'Error fetching odds: {str(e)}', 'danger')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/calculate', methods=['POST'])
@admin_required
def calculate_results(week_id):
    week = db.session.get(Week, week_id)
    if not week:
        flash('Week not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    calculate_week_results(week)
    flash(f'Results calculated for Week {week.week_number}.', 'success')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/complete', methods=['POST'])
@admin_required
def complete_week(week_id):
    week = db.session.get(Week, week_id)
    if week:
        week.is_completed = True
        week.is_open_for_picks = False
        db.session.commit()
        flash(f'Week {week.week_number} marked as completed.', 'success')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/weeks/<int:week_id>/save-scores', methods=['POST'])
@admin_required
def save_scores(week_id):
    week = db.session.get(Week, week_id)
    if not week:
        flash('Week not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    games = Game.query.filter_by(week_id=week.id).all()
    for game in games:
        hs = request.form.get(f'home_score_{game.id}')
        aws = request.form.get(f'away_score_{game.id}')
        if hs is not None and aws is not None and hs != '' and aws != '':
            game.home_score = int(hs)
            game.away_score = int(aws)
            game.is_final = True
    db.session.commit()
    flash(f'Scores saved for Week {week.week_number}.', 'success')
    return redirect(url_for('admin.manage_week', week_id=week_id))


@admin_bp.route('/games/<int:game_id>/delete', methods=['POST'])
@admin_required
def delete_game(game_id):
    game = db.session.get(Game, game_id)
    if game:
        week_id = game.week_id
        Pick.query.filter_by(game_id=game.id).delete()
        db.session.delete(game)
        db.session.commit()
        flash('Game deleted.', 'info')
        return redirect(url_for('admin.manage_week', week_id=week_id))
    return redirect(url_for('admin.seasons'))
