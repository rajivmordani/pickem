from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Season, Week, Game, Pick, WeeklyResult, SeasonEntry
from app.scoring import calculate_week_results, calculate_prize_pool
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
    flash('User created successfully.', 'success')
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


@admin_bp.route('/seasons')
@admin_required
def seasons():
    all_seasons = Season.query.order_by(Season.year.desc()).all()
    return render_template('admin/seasons.html', seasons=all_seasons)


@admin_bp.route('/seasons/create', methods=['POST'])
@admin_required
def create_season():
    year = request.form.get('year', type=int)
    entry_fee = request.form.get('entry_fee', type=int) or 30
    if not year:
        flash('Year is required.', 'danger')
        return redirect(url_for('admin.seasons'))
    if Season.query.filter_by(year=year).first():
        flash(f'Season {year} already exists.', 'danger')
        return redirect(url_for('admin.seasons'))
    Season.query.update({Season.is_active: False})
    season = Season(year=year, is_active=True, entry_fee=entry_fee)
    db.session.add(season)
    db.session.flush()
    for wn in range(1, 19):
        db.session.add(Week(season_id=season.id, week_number=wn))
    db.session.commit()
    flash(f'Season {year} created with 18 weeks and ${entry_fee} entry fee.', 'success')
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
        flash(f'Error fetching odds: {e}', 'danger')
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


@admin_bp.route('/seasons/<int:season_id>/prize-pool')
@admin_required
def prize_pool(season_id):
    season = db.session.get(Season, season_id)
    if not season:
        flash('Season not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    # Get all active users
    users = User.query.filter_by(is_active_player=True).order_by(User.display_name).all()
    
    # Get season entries
    entries = {e.user_id: e for e in SeasonEntry.query.filter_by(season_id=season.id).all()}
    
    # Calculate prize pool
    prize_info = calculate_prize_pool(season)
    
    return render_template('admin/prize_pool.html', 
                         season=season, 
                         users=users, 
                         entries=entries,
                         prize_info=prize_info)


@admin_bp.route('/seasons/<int:season_id>/entries/add-all', methods=['POST'])
@admin_required
def add_all_entries(season_id):
    season = db.session.get(Season, season_id)
    if not season:
        flash('Season not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    users = User.query.filter_by(is_active_player=True).all()
    count = 0
    for user in users:
        existing = SeasonEntry.query.filter_by(season_id=season.id, user_id=user.id).first()
        if not existing:
            entry = SeasonEntry(season_id=season.id, user_id=user.id, has_paid=False)
            db.session.add(entry)
            count += 1
    
    db.session.commit()
    flash(f'Added {count} players to season {season.year}.', 'success')
    return redirect(url_for('admin.prize_pool', season_id=season_id))


@admin_bp.route('/seasons/<int:season_id>/entries/<int:user_id>/toggle-paid', methods=['POST'])
@admin_required
def toggle_entry_paid(season_id, user_id):
    entry = SeasonEntry.query.filter_by(season_id=season_id, user_id=user_id).first()
    if not entry:
        season = db.session.get(Season, season_id)
        if not season:
            flash('Season not found.', 'danger')
            return redirect(url_for('admin.seasons'))
        entry = SeasonEntry(season_id=season_id, user_id=user_id, has_paid=True, amount_paid=season.entry_fee)
        db.session.add(entry)
    else:
        entry.has_paid = not entry.has_paid
        if entry.has_paid and not entry.amount_paid:
            season = db.session.get(Season, season_id)
            entry.amount_paid = season.entry_fee if season else 30
    
    db.session.commit()
    return redirect(url_for('admin.prize_pool', season_id=season_id))


@admin_bp.route('/seasons/<int:season_id>/update-entry-fee', methods=['POST'])
@admin_required
def update_entry_fee(season_id):
    season = db.session.get(Season, season_id)
    if not season:
        flash('Season not found.', 'danger')
        return redirect(url_for('admin.seasons'))
    
    new_fee = request.form.get('entry_fee', type=int)
    if new_fee and new_fee > 0:
        season.entry_fee = new_fee
        db.session.commit()
        flash(f'Entry fee updated to ${new_fee}.', 'success')
    else:
        flash('Invalid entry fee.', 'danger')
    
    return redirect(url_for('admin.prize_pool', season_id=season_id))
