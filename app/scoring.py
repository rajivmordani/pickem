from app import db
from app.models import User, Week, Game, Pick, WeeklyResult, Season


def calculate_week_results(week):
    games = Game.query.filter_by(week_id=week.id).all()
    game_ids = [g.id for g in games]
    if not game_ids:
        return

    for game in games:
        if game.is_final:
            picks = Pick.query.filter_by(game_id=game.id).all()
            for pick in picks:
                pick.points = game.calculate_points(pick.picked_team)
    db.session.flush()

    users = User.query.filter_by(is_active_player=True).all()
    WeeklyResult.query.filter_by(week_id=week.id).delete()

    results = []
    for user in users:
        picks = Pick.query.filter(
            Pick.user_id == user.id,
            Pick.game_id.in_(game_ids)
        ).all()
        if not picks:
            continue
        total_points = sum(p.points or 0 for p in picks)
        winning_picks = sum(1 for p in picks if p.points is not None and p.points > 0)
        is_eligible = len(picks) >= 4

        wr = WeeklyResult(
            user_id=user.id, week_id=week.id,
            total_points=total_points, num_picks=len(picks),
            winning_picks=winning_picks, weekly_win_share=0,
            is_eligible=is_eligible
        )
        results.append(wr)
        db.session.add(wr)
    db.session.flush()

    eligible = [r for r in results if r.is_eligible]
    if not eligible:
        db.session.commit()
        return

    eligible.sort(key=lambda r: r.total_points, reverse=True)
    best_score = eligible[0].total_points
    tied = [r for r in eligible if r.total_points == best_score]

    if len(tied) == 1:
        tied[0].weekly_win_share = 1.0
    else:
        max_winning = max(r.winning_picks for r in tied)
        final_winners = [r for r in tied if r.winning_picks == max_winning]
        share = 1.0 / len(final_winners)
        for r in final_winners:
            r.weekly_win_share = share

    db.session.commit()


def calculate_weekly_prize_winner(season):
    completed_weeks = Week.query.filter_by(
        season_id=season.id, is_completed=True
    ).order_by(Week.week_number).all()

    if not completed_weeks:
        return {'winners': [], 'standings': []}

    user_stats = {}
    users = User.query.filter_by(is_active_player=True).all()
    user_map = {u.id: u for u in users}

    for week in completed_weeks:
        results = WeeklyResult.query.filter_by(week_id=week.id).all()
        for r in results:
            if r.user_id not in user_stats:
                user_stats[r.user_id] = {
                    'user': user_map.get(r.user_id),
                    'total_wins': 0,
                    'winning_picks_in_win_weeks': 0,
                    'win_weeks': [],
                }
            if r.weekly_win_share > 0:
                user_stats[r.user_id]['total_wins'] += r.weekly_win_share
                user_stats[r.user_id]['winning_picks_in_win_weeks'] += r.winning_picks
                user_stats[r.user_id]['win_weeks'].append(week.week_number)

    if not user_stats:
        return {'winners': [], 'standings': []}

    standings = sorted(
        user_stats.values(),
        key=lambda x: (-x['total_wins'], -x['winning_picks_in_win_weeks']),
    )

    with_wins = [s for s in standings if s['total_wins'] > 0]
    if not with_wins:
        return {'winners': [], 'standings': standings}

    best = with_wins[0]
    contenders = [s for s in with_wins
                  if s['total_wins'] == best['total_wins']
                  and s['winning_picks_in_win_weeks'] == best['winning_picks_in_win_weeks']]

    if len(contenders) == 1:
        return {'winners': [contenders[0]], 'standings': standings}

    week_sets = [tuple(sorted(c['win_weeks'])) for c in contenders]
    if len(set(week_sets)) == 1:
        return {'winners': contenders, 'standings': standings}

    best_contender = None
    for wk_num in reversed(range(1, (completed_weeks[-1].week_number if completed_weeks else 0) + 1)):
        in_week = [c for c in contenders if wk_num in c['win_weeks']]
        not_in_week = [c for c in contenders if wk_num not in c['win_weeks']]
        if len(in_week) > 0 and len(not_in_week) > 0:
            best_contender = in_week
            break

    if best_contender:
        return {'winners': best_contender, 'standings': standings}
    return {'winners': contenders, 'standings': standings}


def calculate_yearly_standings(season):
    completed_weeks = Week.query.filter_by(
        season_id=season.id, is_completed=True
    ).order_by(Week.week_number).all()

    if not completed_weeks:
        return []

    users = User.query.filter_by(is_active_player=True).all()
    total_weeks = season.total_weeks
    critical_weeks = [total_weeks, total_weeks - 1]

    standings = []
    for user in users:
        total_points = 0
        total_winning_picks = 0
        total_picks = 0
        weekly_wins = 0
        winning_picks_in_win_weeks = 0
        win_weeks = []
        is_qualified = True

        for week in completed_weeks:
            wr = WeeklyResult.query.filter_by(
                user_id=user.id, week_id=week.id
            ).first()

            if wr:
                total_points += wr.total_points
                total_winning_picks += wr.winning_picks
                total_picks += wr.num_picks
                if wr.weekly_win_share > 0:
                    weekly_wins += wr.weekly_win_share
                    winning_picks_in_win_weeks += wr.winning_picks
                    win_weeks.append(week.week_number)
                if week.week_number in critical_weeks and wr.num_picks < 4:
                    is_qualified = False
            else:
                if week.week_number in critical_weeks:
                    is_qualified = False

        if total_picks == 0:
            continue

        standings.append({
            'user': user,
            'total_points': total_points,
            'total_winning_picks': total_winning_picks,
            'total_picks': total_picks,
            'weekly_wins': weekly_wins,
            'winning_picks_in_win_weeks': winning_picks_in_win_weeks,
            'win_weeks': win_weeks,
            'is_qualified': is_qualified,
        })

    standings.sort(key=lambda x: (
        -int(x['is_qualified']),
        -x['total_points'],
        -x['weekly_wins'],
        -x['winning_picks_in_win_weeks']
    ))

    return standings
