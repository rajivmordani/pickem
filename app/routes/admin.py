from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Game, Pick, WeekResult
from app.forms import AddUserForm, EditUserForm, ImportOddsForm, ManualGameForm

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Administrator access required.', 'danger')
            return redirect(url_for('picks.weekly'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.username).all()
    form = AddUserForm()
    return render_template('admin/users.html', users=all_users, form=form)


@admin_bp.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    form = AddUserForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash(f'Username "{form.username.data}" already exists.', 'danger')
            return redirect(url_for('admin.users'))
        if User.query.filter_by(email=form.email.data).first():
            flash(f'Email "{form.email.data}" already in use.', 'danger')
            return redirect(url_for('admin.users'))
        user = User(username=form.username.data, email=form.email.data, is_admin=form.is_admin.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'User "{user.username}" created successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.users'))
    form = EditUserForm(obj=user)
    if request.method == 'GET':
        form.is_active.data = user.is_active_user
    if form.validate_on_submit():
        user.email = form.email.data
        user.is_admin = form.is_admin.data
        user.is_active_user = form.is_active.data
        if form.password.data:
            user.set_password(form.password.data)
        db.session.commit()
        flash(f'User "{user.username}" updated.', 'success')
        return redirect(url_for('admin.users'))
    return render_template('admin/edit_user.html', user=user, form=form)


@admin_bp.route('/games')
@admin_required
def games():
    season = request.args.get('season', datetime.now().year, type=int)
    week = request.args.get('week', 1, type=int)
    game_list = Game.query.filter_by(season=season, week=week).order_by(Game.game_time).all()
    import_form = ImportOddsForm()
    import_form.season.data = season
    import_form.week.data = week
    manual_form = ManualGameForm()
    manual_form.season.data = season
    manual_form.week.data = week
    return render_template('admin/games.html', games=game_list, season=season, week=week, import_form=import_form, manual_form=manual_form)


@admin_bp.route('/games/import', methods=['POST'])
@admin_required
def import_odds():
    form = ImportOddsForm()
    if form.validate_on_submit():
        week = form.week.data
        season = form.season.data
        try:
            from app.services.odds import fetch_odds, determine_nfl_week
            odds_data = fetch_odds()
            count = 0
            for g in odds_data:
                game_week = determine_nfl_week(g['game_time'], season)
                if game_week != week:
                    continue
                existing = Game.query.filter_by(api_id=g['api_id']).first() if g['api_id'] else None
                if existing:
                    existing.spread = g['spread']
                    existing.game_time = g['game_time']
                else:
                    game = Game(week=week, season=season, home_team=g['home_team'], away_team=g['away_team'], spread=g['spread'], game_time=g['game_time'], api_id=g['api_id'])
                    db.session.add(game)
                count += 1
            db.session.commit()
            flash(f'Imported/updated {count} games for Week {week}.', 'success')
        except Exception as e:
            flash(f'Error importing odds: {str(e)}', 'danger')
    return redirect(url_for('admin.games', season=form.season.data, week=form.week.data))


@admin_bp.route('/games/add', methods=['POST'])
@admin_required
def add_game():
    form = ManualGameForm()
    if form.validate_on_submit():
        try:
            game_time = datetime.strptime(form.game_time.data, '%Y-%m-%d %H:%M')
            game_time = game_time.replace(tzinfo=timezone.utc)
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD HH:MM', 'danger')
            return redirect(url_for('admin.games', season=form.season.data, week=form.week.data))
        game = Game(week=form.week.data, season=form.season.data, home_team=form.home_team.data, away_team=form.away_team.data, spread=form.spread.data, game_time=game_time)
        db.session.add(game)
        db.session.commit()
        flash(f'{game.away_team} @ {game.home_team} added.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'danger')
    return redirect(url_for('admin.games', season=form.season.data, week=form.week.data))


@admin_bp.route('/games/<int:game_id>/delete', methods=['POST'])
@admin_required
def delete_game(game_id):
    game = db.session.get(Game, game_id)
    if game:
        Pick.query.filter_by(game_id=game.id).delete()
        db.session.delete(game)
        db.session.commit()
        flash('Game deleted.', 'info')
    return redirect(request.referrer or url_for('admin.games'))


@admin_bp.route('/scores')
@admin_required
def scores():
    season = request.args.get('season', datetime.now().year, type=int)
    week = request.args.get('week', 1, type=int)
    game_list = Game.query.filter_by(season=season, week=week).order_by(Game.game_time).all()
    return render_template('admin/scores.html', games=game_list, season=season, week=week)


@admin_bp.route('/scores/save', methods=['POST'])
@admin_required
def save_scores():
    season = request.form.get('season', datetime.now().year, type=int)
    week = request.form.get('week', 1, type=int)
    game_list = Game.query.filter_by(season=season, week=week).all()
    for game in game_list:
        hs = request.form.get(f'home_score_{game.id}')
        aws = request.form.get(f'away_score_{game.id}')
        if hs is not None and aws is not None and hs != '' and aws != '':
            game.home_score = int(hs)
            game.away_score = int(aws)
            game.is_final = True
    db.session.commit()
    flash(f'Scores saved for Week {week}.', 'success')
    return redirect(url_for('admin.scores', season=season, week=week))


@admin_bp.route('/recalculate', methods=['POST'])
@admin_required
def recalculate():
    season = request.form.get('season', datetime.now().year, type=int)
    week = request.form.get('week', 0, type=int)
    from app.services.scoring import recalculate_week
    if week > 0:
        recalculate_week(season, week)
        flash(f'Week {week} results recalculated.', 'success')
    else:
        weeks = db.session.query(Game.week).filter_by(season=season).distinct().all()
        for (w,) in weeks:
            recalculate_week(season, w)
        flash(f'All weeks in {season} recalculated.', 'success')
    return redirect(url_for('standings.weekly', season=season, week=week if week > 0 else 1))
