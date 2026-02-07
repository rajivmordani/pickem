"""
Scoring engine implementing the full pick'em rules:
- Rule 2: Points calculation (clamped -15 to +15)
- Rule 3: Picking process constraints
- Rule 4: Weekly winner determination
- Rule 5: Weekly prize winner (season-long weekly competition)
- Rule 6: Yearly prize winner
"""

from collections import defaultdict
from app import db
from app.models import User, Game, Pick, WeekResult


# ── Rule 2: Points Calculation ───────────────────────────────────

def calculate_pick_points(game, picked_team):
    """
    Calculate points for a single pick.

    spread is positive when home team is favored.
    Points = how much better the picked team did vs the spread.
    Clamped to [-15, +15].

    Example: Dolphins (home) favored by 10 (spread=10).
    - Dolphins win by 3: pick Dolphins = 3-10 = -7; pick Jets = +7
    - Dolphins win by 13: pick Dolphins = 13-10 = +3; pick Jets = -3
    """
    if game.home_score is None or game.away_score is None:
        return 0

    actual_margin = game.home_score - game.away_score  # positive = home won

    if picked_team == game.home_team:
        raw = actual_margin - game.spread
    else:
        raw = game.spread - actual_margin

    return max(-15, min(15, raw))


# ── Rule 4: Weekly Winner ────────────────────────────────────────

def recalculate_week(season, week):
    """
    Recalculate results for a specific week.

    1. For each user who made picks, compute total points and winning picks count.
    2. Among users with >= 4 picks, determine the weekly winner(s).
    3. Ties broken by number of winning picks (points > 0).
    4. If still tied, split the win equally.
    """
    games = Game.query.filter_by(season=season, week=week, is_final=True).all()
    game_ids = [g.id for g in games]
    game_map = {g.id: g for g in games}

    if not game_ids:
        return

    picks = Pick.query.filter(Pick.game_id.in_(game_ids)).all()

    user_picks = defaultdict(list)
    for pick in picks:
        user_picks[pick.user_id].append(pick)

    user_stats = {}
    for user_id, user_pick_list in user_picks.items():
        total_points = 0.0
        winning_count = 0
        for pick in user_pick_list:
            game = game_map.get(pick.game_id)
            if game:
                pts = calculate_pick_points(game, pick.picked_team)
                total_points += pts
                if pts > 0:
                    winning_count += 1
        user_stats[user_id] = {
            'total_points': total_points,
            'winning_picks_count': winning_count,
            'num_picks': len(user_pick_list),
        }

    WeekResult.query.filter_by(season=season, week=week).delete()

    eligible = {uid: stats for uid, stats in user_stats.items() if stats['num_picks'] >= 4}

    weekly_winners = []
    if eligible:
        sorted_eligible = sorted(
            eligible.items(),
            key=lambda x: (x[1]['total_points'], x[1]['winning_picks_count']),
            reverse=True,
        )
        best_points = sorted_eligible[0][1]['total_points']

        top_tied = [
            (uid, stats) for uid, stats in sorted_eligible
            if stats['total_points'] == best_points
        ]

        if len(top_tied) == 1:
            weekly_winners = [top_tied[0][0]]
        else:
            max_winning = max(s['winning_picks_count'] for _, s in top_tied)
            winners_by_wp = [uid for uid, s in top_tied if s['winning_picks_count'] == max_winning]
            weekly_winners = winners_by_wp

    win_share = 1.0 / len(weekly_winners) if weekly_winners else 0.0

    for user_id, stats in user_stats.items():
        wr = WeekResult(
            user_id=user_id,
            week=week,
            season=season,
            total_points=stats['total_points'],
            winning_picks_count=stats['winning_picks_count'],
            weekly_wins=win_share if user_id in weekly_winners else 0.0,
        )
        db.session.add(wr)

    db.session.commit()


# ── Rule 5: Weekly Prize Winner ──────────────────────────────────

def determine_weekly_prize_winner(season):
    """
    Determine the weekly prize winner for the season.

    5a) Most weekly wins
    5b) Tiebreak: most winning picks in winning weeks
    5c) Tiebreak: latest weekly win not shared
    5d) Same weeks -> split
    """
    results = WeekResult.query.filter_by(season=season).all()

    user_data = defaultdict(lambda: {
        'total_weekly_wins': 0.0,
        'winning_picks_in_win_weeks': 0,
        'win_weeks': [],
    })

    for r in results:
        data = user_data[r.user_id]
        if r.weekly_wins > 0:
            data['total_weekly_wins'] += r.weekly_wins
            data['winning_picks_in_win_weeks'] += r.winning_picks_count
            data['win_weeks'].append(r.week)

    if not user_data:
        return []

    candidates = sorted(user_data.items(), key=lambda x: x[1]['total_weekly_wins'], reverse=True)
    best_wins = candidates[0][1]['total_weekly_wins']

    if best_wins == 0:
        return []

    top_tied = [(uid, d) for uid, d in candidates if d['total_weekly_wins'] == best_wins]

    if len(top_tied) == 1:
        return top_tied

    max_wp = max(d['winning_picks_in_win_weeks'] for _, d in top_tied)
    top_tied = [(uid, d) for uid, d in top_tied if d['winning_picks_in_win_weeks'] == max_wp]

    if len(top_tied) == 1:
        return top_tied

    all_win_weeks = [set(d['win_weeks']) for _, d in top_tied]
    common_weeks = set.intersection(*all_win_weeks)
    all_weeks = set.union(*all_win_weeks)

    differentiating_weeks = sorted(all_weeks - common_weeks, reverse=True)

    for wk in differentiating_weeks:
        players_with_wk = [(uid, d) for uid, d in top_tied if wk in d['win_weeks']]
        if len(players_with_wk) < len(top_tied):
            return players_with_wk

    return top_tied


# ── Rule 6: Yearly Prize Winner ──────────────────────────────────

def determine_yearly_prize_winner(season):
    """
    Determine the yearly prize winner.

    6a) Most total points among qualified players.
    6b) Tiebreak: weekly competition ranking.
    6c) Still tied: split.

    Disqualified: < 4 picks in either of the last two weeks.
    """
    last_weeks_q = (
        db.session.query(Game.week)
        .filter_by(season=season)
        .distinct()
        .order_by(Game.week.desc())
        .limit(2)
        .all()
    )
    last_two_weeks = [w[0] for w in last_weeks_q]

    all_users = User.query.filter_by(is_active_user=True).all()
    user_ids = [u.id for u in all_users]

    qualified_ids = set(user_ids)
    for week_num in last_two_weeks:
        games_in_week = Game.query.filter_by(season=season, week=week_num).all()
        game_ids = [g.id for g in games_in_week]
        if not game_ids:
            continue
        for uid in list(qualified_ids):
            pick_count = Pick.query.filter(
                Pick.user_id == uid,
                Pick.game_id.in_(game_ids)
            ).count()
            if pick_count < 4:
                qualified_ids.discard(uid)

    if not qualified_ids:
        return []

    results = WeekResult.query.filter(
        WeekResult.season == season,
        WeekResult.user_id.in_(qualified_ids)
    ).all()

    user_totals = defaultdict(lambda: {'total_points': 0.0, 'user_id': None})
    for r in results:
        user_totals[r.user_id]['total_points'] += r.total_points
        user_totals[r.user_id]['user_id'] = r.user_id

    if not user_totals:
        return []

    candidates = sorted(user_totals.items(), key=lambda x: x[1]['total_points'], reverse=True)
    best = candidates[0][1]['total_points']
    top_tied = [(uid, d) for uid, d in candidates if d['total_points'] == best]

    if len(top_tied) == 1:
        return top_tied

    weekly_ranking = determine_weekly_prize_winner(season)
    weekly_ranked_ids = [uid for uid, _ in weekly_ranking]

    for ranked_uid in weekly_ranked_ids:
        matches = [(uid, d) for uid, d in top_tied if uid == ranked_uid]
        if matches:
            return matches

    return top_tied


# ── Prize Calculation (Rule 1) ───────────────────────────────────

def calculate_prizes(season):
    """Calculate prize amounts."""
    from flask import current_app
    entry_fee = current_app.config.get('ENTRY_FEE', 30)

    num_players = User.query.filter_by(is_active_user=True).count()
    pool = num_players * entry_fee

    yearly_winners = determine_yearly_prize_winner(season)
    weekly_winners = determine_weekly_prize_winner(season)

    winner_ids = set()
    for uid, _ in yearly_winners:
        winner_ids.add(uid)
    for uid, _ in weekly_winners:
        winner_ids.add(uid)

    num_winners = len(winner_ids)
    remaining = pool - (entry_fee * num_winners)
    remaining = max(0, remaining)

    yearly_prize = (2 / 3) * remaining
    weekly_prize = (1 / 3) * remaining

    yearly_per_person = yearly_prize / len(yearly_winners) if yearly_winners else 0
    weekly_per_person = weekly_prize / len(weekly_winners) if weekly_winners else 0

    return {
        'pool': pool,
        'entry_fee': entry_fee,
        'num_players': num_players,
        'remaining': remaining,
        'yearly_winners': yearly_winners,
        'weekly_winners': weekly_winners,
        'yearly_prize_total': yearly_prize,
        'weekly_prize_total': weekly_prize,
        'yearly_prize_per_person': yearly_per_person,
        'weekly_prize_per_person': weekly_per_person,
    }
