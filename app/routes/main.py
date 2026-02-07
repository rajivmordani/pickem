from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Season, Week

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    season = Season.query.filter_by(is_active=True).first()
    cw = None
    if season:
        cw = Week.query.filter_by(season_id=season.id, is_completed=False).order_by(Week.week_number).first()
        if cw is None:
            cw = Week.query.filter_by(season_id=season.id).order_by(Week.week_number.desc()).first()
    return render_template('main/index.html', season=season, current_week=cw)
