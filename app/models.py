from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_player = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    picks = db.relationship("Pick", backref="user", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Season(db.Model):
    __tablename__ = "seasons"
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    total_weeks = db.Column(db.Integer, default=18)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    weeks = db.relationship("Week", backref="season", lazy="dynamic", order_by="Week.week_number")


class Week(db.Model):
    __tablename__ = "weeks"
    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    is_open_for_picks = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    picks_deadline = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    games = db.relationship("Game", backref="week", lazy="dynamic", order_by="Game.game_time")
    __table_args__ = (db.UniqueConstraint("season_id", "week_number", name="uq_season_week"),)

    @property
    def is_last_or_second_to_last(self):
        return self.week_number >= self.season.total_weeks - 1


class Game(db.Model):
    __tablename__ = "games"
    id = db.Column(db.Integer, primary_key=True)
    week_id = db.Column(db.Integer, db.ForeignKey("weeks.id"), nullable=False)
    home_team = db.Column(db.String(64), nullable=False)
    away_team = db.Column(db.String(64), nullable=False)
    spread = db.Column(db.Float, nullable=True)
    favorite = db.Column(db.String(10), nullable=True)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    game_time = db.Column(db.DateTime, nullable=True)
    is_final = db.Column(db.Boolean, default=False)
    espn_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    picks = db.relationship("Pick", backref="game", lazy="dynamic")

    @property
    def has_started(self):
        return self.game_time is not None and datetime.now(timezone.utc) >= self.game_time

    @property
    def spread_display(self):
        if self.spread is None: return "N/A"
        sv = abs(self.spread)
        return f"{self.home_team} -{sv}" if self.favorite == "home" else f"{self.away_team} -{sv}"

    @property
    def underdog(self):
        if self.favorite == "home": return self.away_team
        if self.favorite == "away": return self.home_team
        return None

    @property
    def favored_team(self):
        if self.favorite == "home": return self.home_team
        if self.favorite == "away": return self.away_team
        return None

    def calculate_points(self, picked_team):
        if self.home_score is None or self.away_score is None or self.spread is None: return None
        sv = abs(self.spread)
        margin = (self.home_score - self.away_score) if self.favorite == "home" else (self.away_score - self.home_score)
        fp = margin - sv
        rp = fp if picked_team == self.favored_team else -fp
        return max(-15, min(15, rp))


class Pick(db.Model):
    __tablename__ = "picks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=False)
    picked_team = db.Column(db.String(64), nullable=False)
    points = db.Column(db.Float, nullable=True)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("user_id", "game_id", name="uq_user_game"),)

    @property
    def is_winning_pick(self):
        return self.points is not None and self.points > 0


class PickViewLog(db.Model):
    __tablename__ = "pick_view_log"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("weeks.id"), nullable=False)
    viewed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("user_id", "week_id", name="uq_user_week_view"),)


class WeeklyResult(db.Model):
    __tablename__ = "weekly_results"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    week_id = db.Column(db.Integer, db.ForeignKey("weeks.id"), nullable=False)
    total_points = db.Column(db.Float, default=0)
    num_picks = db.Column(db.Integer, default=0)
    winning_picks = db.Column(db.Integer, default=0)
    weekly_win_share = db.Column(db.Float, default=0)
    is_eligible = db.Column(db.Boolean, default=True)
    user = db.relationship("User", backref="weekly_results")
    week = db.relationship("Week", backref="weekly_results")
    __table_args__ = (db.UniqueConstraint("user_id", "week_id", name="uq_user_week_result"),)
