from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models import Season, Week, WeeklyResult
from app.scoring import calculate_weekly_prize_winner, calculate_yearly_standings, calculate_prize_pool

standings_bp = Blueprint('standings', __name__)


@standings_bp.route('/')
@login_required
def index():
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        flash('No active season.', 'warning')
        return redirect(url_for('main.index'))
    return redirect(url_for('standings.yearly', season_id=season.id))


@standings_bp.route('/yearly/<int:season_id>')
@login_required
def yearly(season_id):
    season = db.session.get(Season, season_id)
    if not season:
        flash('Season not found.', 'danger')
        return redirect(url_for('standings.index'))
    standings = calculate_yearly_standings(season)
    weekly_prize_info = calculate_weekly_prize_winner(season)
    prize_pool = calculate_prize_pool(season)
    weeks = Week.query.filter_by(season_id=season.id, is_completed=True).order_by(Week.week_number).all()
    weekly_data = {}
    for w in weeks:
        for wr in WeeklyResult.query.filter_by(week_id=w.id).all():
            weekly_data.setdefault(wr.user_id, {})[w.week_number] = wr
    return render_template(
        'standings/yearly.html',
        season=season, standings=standings, weekly_prize_info=weekly_prize_info,
        weeks=weeks, weekly_data=weekly_data, prize_pool=prize_pool,
    )


@standings_bp.route('/weekly/<int:season_id>')
@login_required
def weekly(season_id):
    season = db.session.get(Season, season_id)
    if not season:
        flash('Season not found.', 'danger')
        return redirect(url_for('standings.index'))
    weeks = Week.query.filter_by(season_id=season.id, is_completed=True).order_by(Week.week_number).all()
    weekly_winners = {}
    for w in weeks:
        results = (
            WeeklyResult.query.filter_by(week_id=w.id)
            .order_by(WeeklyResult.total_points.desc()).all()
        )
        winners = [r for r in results if r.weekly_win_share > 0]
        weekly_winners[w.id] = {'results': results, 'winners': winners}
    return render_template(
        'standings/weekly.html',
        season=season, weeks=weeks, weekly_winners=weekly_winners,
    )
