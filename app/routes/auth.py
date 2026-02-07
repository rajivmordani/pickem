from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app import db

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember_me'))
        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))
        if not user.is_active_player:
            flash('Your account has been deactivated.', 'warning')
            return redirect(url_for('auth.login'))
        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.index'))
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        if not current_user.check_password(current_pw):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.change_password'))
        if len(new_pw) < 4:
            flash('New password must be at least 4 characters.', 'danger')
            return redirect(url_for('auth.change_password'))
        current_user.set_password(new_pw)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        return redirect(url_for('main.index'))
    return render_template('auth/change_password.html')
