from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField,
    IntegerField, FloatField, HiddenField
)
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class AddUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=4)])
    is_admin = BooleanField('Administrator')
    submit = SubmitField('Add User')


class EditUserForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('New Password (leave blank to keep current)', validators=[Optional(), Length(min=4)])
    is_admin = BooleanField('Administrator')
    is_active = BooleanField('Active')
    submit = SubmitField('Update User')


class ImportOddsForm(FlaskForm):
    week = IntegerField('NFL Week', validators=[DataRequired(), NumberRange(min=1, max=18)])
    season = IntegerField('Season Year', validators=[DataRequired(), NumberRange(min=2020, max=2030)])
    submit = SubmitField('Import Spreads')


class ManualGameForm(FlaskForm):
    week = IntegerField('NFL Week', validators=[DataRequired(), NumberRange(min=1, max=18)])
    season = IntegerField('Season Year', validators=[DataRequired(), NumberRange(min=2020, max=2030)])
    home_team = StringField('Home Team', validators=[DataRequired()])
    away_team = StringField('Away Team', validators=[DataRequired()])
    spread = FloatField('Spread (positive = home favored)', validators=[DataRequired()])
    game_time = StringField('Game Time (YYYY-MM-DD HH:MM)', validators=[DataRequired()])
    submit = SubmitField('Add Game')


class EnterScoreForm(FlaskForm):
    game_id = HiddenField('Game ID', validators=[DataRequired()])
    home_score = IntegerField('Home Score', validators=[DataRequired(), NumberRange(min=0)])
    away_score = IntegerField('Away Score', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Save Score')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=4)])
    submit = SubmitField('Change Password')
