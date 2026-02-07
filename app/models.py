from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_user = db.Column(db.Boolean, default=True)
    picks = db.relationship('Pick', backref='user', lazy='dynamic')
    week_results = db.relationship('WeekResult', backref='user', lazy='dynamic')
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    @property
    def is_active(self):
        return self.is_active_user
    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    week = db.Column(db.Integer, nullable=False, index=True)
    season = db.Column(db.Integer, nullable=False, index=True)
    home_team = db.Column(db.String(64), nullable=False)
    away_team = db.Column(db.String(64), nullable=False)
    spread = db.Column(db.Float, nullable=False)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    game_time = db.Column(db.DateTime, nullable=False)
    is_final = db.Column(db.Boolean, default=False)
    api_id = db.Column(db.String(128), nullable=True, unique=True)
    picks = db.relationship('Pick', backref='game', lazy='dynamic')
    @property
    def has_started(self):
        now = datetime.now(timezone.utc)
        gt = self.game_time
        if gt.tzinfo is None:
            gt = gt.replace(tzinfo=timezone.utc)
        return now >= gt
    @property
    def favorite(self):
        if self.spread > 0: return self.home_team
        elif self.spread < 0: return self.away_team
        return None
    @property
    def underdog(self):
        if self.spread > 0: return self.away_team
        elif self.spread < 0: return self.home_team
        return None
    @property
    def spread_display(self):
        if self.spread == 0: return "Even"
        fav = self.favorite
        pts = abs(self.spread)
        return f"{fav} -{pts:g}"
    def __repr__(self):
        return f'<Game {self.away_team} @ {self.home_team} Wk{self.week}>'


class Pick(db.Model):
    __tablename__ = 'picks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    picked_team = db.Column(db.String(64), nullable=False)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('user_id', 'game_id', name='uq_user_game'),)
    def __repr__(self):
        return f'<Pick user={self.user_id} game={self.game_id}>'


class WeekResult(db.Model):
    __tablename__ = 'week_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    season = db.Column(db.Integer, nullable=False)
    total_points = db.Column(db.Float, default=0.0)
    winning_picks_count = db.Column(db.Integer, default=0)
    weekly_wins = db.Column(db.Float, default=0.0)
    __table_args__ = (db.UniqueConstraint('user_id', 'week', 'season', name='uq_user_week_season'),)
    def __repr__(self):
        return f'<WeekResult user={self.user_id} wk={self.week}>'
