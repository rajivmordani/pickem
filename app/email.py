from flask import current_app
from flask_mail import Mail, Message
from datetime import datetime

mail = Mail()


def init_mail(app):
    """Initialize Flask-Mail with the app"""
    mail.init_app(app)


def send_picks_confirmation(user, week, picks_data):
    """
    Send a confirmation email to a user after they submit picks.
    
    Args:
        user: User object
        week: Week object
        picks_data: List of dicts with pick information
    """
    if not current_app.config.get('MAIL_ENABLED'):
        # Email not configured, skip silently
        return False
    
    try:
        subject = f"NFL Pick'em - Your Week {week.week_number} Picks"
        
        # Build email body
        body_lines = [
            f"Hi {user.display_name},",
            "",
            f"Your picks for Week {week.week_number} of the {week.season.year} season have been submitted:",
            "",
        ]
        
        for pick in picks_data:
            game_info = f"{pick['away_team']} @ {pick['home_team']}"
            spread_info = f" (Spread: {pick['spread_display']})" if pick.get('spread_display') else ""
            body_lines.append(f"  • {pick['picked_team']} - {game_info}{spread_info}")
        
        body_lines.extend([
            "",
            f"Total picks: {len(picks_data)}",
            "",
            "IMPORTANT REMINDERS:",
            "- You can resubmit your picks ONLY if you haven't viewed other players' picks",
            "- Once you view other picks, your selections are final",
            "- You need at least 4 picks to be eligible for weekly prizes",
            "- Games lock when they start - you cannot pick games that have already begun",
            "",
            f"Submitted at: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}",
            "",
            "Good luck!",
            "",
            "---",
            "NFL Pick'em Pool",
        ])
        
        body = "\n".join(body_lines)
        
        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )
        
        mail.send(msg)
        return True
        
    except Exception as e:
        # Log error but don't fail the pick submission
        current_app.logger.error(f"Failed to send email to {user.email}: {str(e)}")
        return False
