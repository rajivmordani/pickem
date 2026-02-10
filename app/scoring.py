from app import db
from app.models import User, Week, Game, Pick, WeeklyResult, SeasonEntry


def calculate_week_results(week):
    games = Game.query.filter_by(week_id=week.id).all()
    gids = [g.id for g in games]
    if not gids:
        return
    for g in games:
        if g.is_final:
            for p in Pick.query.filter_by(game_id=g.id).all():
                p.points = g.calculate_points(p.picked_team)
    db.session.flush()
    WeeklyResult.query.filter_by(week_id=week.id).delete()
    results = []
    for u in User.query.filter_by(is_active_player=True).all():
        ps = Pick.query.filter(Pick.user_id == u.id, Pick.game_id.in_(gids)).all()
        if not ps:
            continue
        tp = sum(p.points or 0 for p in ps)
        wp = sum(1 for p in ps if p.points is not None and p.points > 0)
        wr = WeeklyResult(user_id=u.id, week_id=week.id, total_points=tp,
                          num_picks=len(ps), winning_picks=wp, weekly_win_share=0,
                          is_eligible=len(ps) >= 4)
        results.append(wr)
        db.session.add(wr)
    db.session.flush()
    eligible = [r for r in results if r.is_eligible]
    if not eligible:
        db.session.commit()
        return
    eligible.sort(key=lambda r: r.total_points, reverse=True)
    best = eligible[0].total_points
    tied = [r for r in eligible if r.total_points == best]
    if len(tied) == 1:
        tied[0].weekly_win_share = 1.0
    else:
        mw = max(r.winning_picks for r in tied)
        fw = [r for r in tied if r.winning_picks == mw]
        share = 1.0 / len(fw)
        for r in fw:
            r.weekly_win_share = share
    db.session.commit()


def calculate_weekly_prize_winner(season):
    cw = Week.query.filter_by(season_id=season.id, is_completed=True).order_by(Week.week_number).all()
    if not cw:
        return {'winners': [], 'standings': []}
    us = {}
    um = {u.id: u for u in User.query.filter_by(is_active_player=True).all()}
    for w in cw:
        for r in WeeklyResult.query.filter_by(week_id=w.id).all():
            us.setdefault(r.user_id, {'user': um.get(r.user_id), 'total_wins': 0,
                                       'winning_picks_in_win_weeks': 0, 'win_weeks': []})
            if r.weekly_win_share > 0:
                us[r.user_id]['total_wins'] += r.weekly_win_share
                us[r.user_id]['winning_picks_in_win_weeks'] += r.winning_picks
                us[r.user_id]['win_weeks'].append(w.week_number)
    if not us:
        return {'winners': [], 'standings': []}
    st = sorted(us.values(), key=lambda x: (-x['total_wins'], -x['winning_picks_in_win_weeks']))
    ww = [s for s in st if s['total_wins'] > 0]
    if not ww:
        return {'winners': [], 'standings': st}
    b = ww[0]
    ct = [s for s in ww if s['total_wins'] == b['total_wins'] and s['winning_picks_in_win_weeks'] == b['winning_picks_in_win_weeks']]
    if len(ct) == 1:
        return {'winners': [ct[0]], 'standings': st}
    ws = [tuple(sorted(c['win_weeks'])) for c in ct]
    if len(set(ws)) == 1:
        return {'winners': ct, 'standings': st}
    for wn in reversed(range(1, (cw[-1].week_number if cw else 0) + 1)):
        iw = [c for c in ct if wn in c['win_weeks']]
        nw = [c for c in ct if wn not in c['win_weeks']]
        if iw and nw:
            return {'winners': iw, 'standings': st}
    return {'winners': ct, 'standings': st}


def calculate_yearly_standings(season):
    cw = Week.query.filter_by(season_id=season.id, is_completed=True).order_by(Week.week_number).all()
    if not cw:
        return []
    users = User.query.filter_by(is_active_player=True).all()
    tw = season.total_weeks
    crit = [tw, tw - 1]
    st = []
    for u in users:
        tp = twp = tpk = ww = wpww = 0
        wwl = []
        qual = True
        for w in cw:
            wr = WeeklyResult.query.filter_by(user_id=u.id, week_id=w.id).first()
            if wr:
                tp += wr.total_points
                twp += wr.winning_picks
                tpk += wr.num_picks
                if wr.weekly_win_share > 0:
                    ww += wr.weekly_win_share
                    wpww += wr.winning_picks
                    wwl.append(w.week_number)
                if w.week_number in crit and wr.num_picks < 4:
                    qual = False
            elif w.week_number in crit:
                qual = False
        if tpk == 0:
            continue
        st.append({'user': u, 'total_points': tp, 'total_winning_picks': twp, 'total_picks': tpk,
                   'weekly_wins': ww, 'winning_picks_in_win_weeks': wpww, 'win_weeks': wwl,
                   'is_qualified': qual})
    st.sort(key=lambda x: (-int(x['is_qualified']), -x['total_points'], -x['weekly_wins'], -x['winning_picks_in_win_weeks']))
    return st


def get_yearly_winners(season):
    """Get yearly prize winners from the yearly standings."""
    standings = calculate_yearly_standings(season)
    if not standings:
        return []
    
    # Get qualified players
    qualified = [s for s in standings if s['is_qualified']]
    if not qualified:
        return []
    
    # Get best score
    best = qualified[0]
    
    # Get all tied with best score
    winners = [s for s in qualified if 
               s['total_points'] == best['total_points'] and 
               s['weekly_wins'] == best['weekly_wins'] and 
               s['winning_picks_in_win_weeks'] == best['winning_picks_in_win_weeks']]
    
    return winners


def calculate_prize_pool(season):
    """
    Calculate prize pool distribution based on entry fees and winners.

    Rules (1c-1f):
    - Each winner gets their entry fee refunded (one refund per unique person).
    - The "remaining entry fees" are computed by subtracting one refund slot
      per prize category (yearly + weekly = 2 slots), regardless of whether
      the same person wins both.
    - Yearly winners split 2/3 of the remaining.
    - Weekly winners split 1/3 of the remaining.

    Example with 8 players at $30 ($240 pool):
      remaining = $240 - 2*$30 = $180
      yearly prize = $180 * 2/3 = $120
      weekly prize = $180 * 1/3 = $60
      Different winners: yearly person gets $30+$120=$150, weekly person gets $30+$60=$90
      Same winner: one person gets $30+$120+$60 = $210
    """
    entries = SeasonEntry.query.filter_by(season_id=season.id, has_paid=True).all()

    if not entries:
        return {
            'total_pool': 0,
            'num_players': 0,
            'entry_fee': season.entry_fee,
            'yearly_winners': [],
            'weekly_winners': [],
            'yearly_prize_per_winner': 0,
            'weekly_prize_per_winner': 0,
            'yearly_total': 0,
            'weekly_total': 0,
            'total_refunds': 0,
            'remaining_after_refunds': 0,
        }

    total_pool = sum(e.amount_paid or season.entry_fee for e in entries)
    num_players = len(entries)

    # Get winners
    yearly_winners = get_yearly_winners(season)
    weekly_prize_info = calculate_weekly_prize_winner(season)
    weekly_winners = weekly_prize_info['winners']

    # "Remaining entry fees" always reserves 2 refund slots (one per prize
    # category) so the prize amounts stay constant regardless of overlap.
    num_refund_slots = 0
    if yearly_winners:
        num_refund_slots += 1
    if weekly_winners:
        num_refund_slots += 1
    remaining = max(0, total_pool - num_refund_slots * season.entry_fee)

    yearly_share = remaining * (2.0 / 3.0)
    weekly_share = remaining * (1.0 / 3.0)

    yearly_per_winner = yearly_share / len(yearly_winners) if yearly_winners else 0
    weekly_per_winner = weekly_share / len(weekly_winners) if weekly_winners else 0

    # Unique winner user IDs (for refund calculation)
    yearly_user_ids = set(w['user'].id for w in yearly_winners if w.get('user'))
    weekly_user_ids = set(w['user'].id for w in weekly_winners if w.get('user'))
    all_winner_ids = yearly_user_ids | weekly_user_ids
    total_refunds = len(all_winner_ids) * season.entry_fee

    # Build per-winner breakdown
    yearly_winners_with_prizes = []
    for w in yearly_winners:
        user = w['user']
        is_also_weekly = user.id in weekly_user_ids
        total_prize = season.entry_fee + yearly_per_winner
        if is_also_weekly:
            total_prize += weekly_per_winner
        yearly_winners_with_prizes.append({
            **w,
            'prize_amount': total_prize,
            'yearly_prize': yearly_per_winner,
            'weekly_prize': weekly_per_winner if is_also_weekly else 0,
            'refund': season.entry_fee,
            'is_also_weekly_winner': is_also_weekly,
        })

    weekly_winners_with_prizes = []
    for w in weekly_winners:
        user = w['user']
        is_also_yearly = user.id in yearly_user_ids
        if not is_also_yearly:
            total_prize = season.entry_fee + weekly_per_winner
            weekly_winners_with_prizes.append({
                **w,
                'prize_amount': total_prize,
                'yearly_prize': 0,
                'weekly_prize': weekly_per_winner,
                'refund': season.entry_fee,
                'is_also_yearly_winner': False,
            })

    return {
        'total_pool': total_pool,
        'num_players': num_players,
        'entry_fee': season.entry_fee,
        'yearly_winners': yearly_winners_with_prizes,
        'weekly_winners': weekly_winners_with_prizes,
        'yearly_prize_per_winner': yearly_per_winner,
        'weekly_prize_per_winner': weekly_per_winner,
        'yearly_total': yearly_share,
        'weekly_total': weekly_share,
        'total_refunds': total_refunds,
        'remaining_after_refunds': remaining,
    }
