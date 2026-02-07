from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app.models import Season, Week, WeeklyResult
from app.scoring import calculate_yearly_standings, calculate_weekly_prize_winner

standings_bp = Blueprint('standings', __name__)


@standings_bp.route('/')
@login_required
def index():
    season = Season.query.filter_by(is_active=True).first()
    if not season:
        flash('No active season.', 'info')
        return redirect(url_for('main.index'))
    return redirect(url_for('standings.yearly', season_id=season.id))


@standings_bp.route('/yearly/<int:season_id>')
@login_required
def yearly(season_id):
    season = Season.query.get_or_404(season_id)
    weeks = Week.query.filter_by(season_id=season_id, is_completed=True).order_by(Week.week_number).all()
    standings = calculate_yearly_standings(season)
    wpi = calculate_weekly_prize_winner(season)
    wd = {}
    for w in weeks:
        for r in WeeklyResult.query.filter_by(week_id=w.id).all():
            wd.setdefault(r.user_id, {})[w.week_number] = r
    return render_template('standings/yearly.html', season=season, weeks=weeks,
                           standings=standings, weekly_data=wd, weekly_prize_info=wpi)


@standings_bp.route('/weekly/<int:season_id>')
@login_required
def weekly(season_id):
    season = Season.query.get_or_404(season_id)
    weeks = Week.query.filter_by(season_id=season_id, is_completed=True).order_by(Week.week_number).all()
    ww = {}
    for w in weeks:
        rs = WeeklyResult.query.filter_by(week_id=w.id).all()
        ww[w.id] = {
            'winners': [r for r in rs if r.weekly_win_share > 0],
            'results': sorted(rs, key=lambda r: (-r.total_points, -r.winning_picks))
        }
    return render_template('standings/weekly.html', season=season, weeks=weeks, weekly_winners=ww)
