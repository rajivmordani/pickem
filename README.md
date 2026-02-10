# NFL Pick'em Pool

A web application for running an NFL pick'em pool with spread-based scoring and prize money tracking.

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

Visit http://localhost:5050 in your browser.

## Default Admin Login

- **Username:** `admin`
- **Password:** `admin123`

Change the admin password after first login.

## Features

- **User Management**: Admin can add/deactivate users and reset passwords
- **Season/Week Management**: Create NFL seasons with 18 weeks, configurable entry fee
- **Odds Fetching**: Auto-fetch spreads from ESPN and The Odds API
- **Pick Submission**: Players pick games against the spread, all at once per week
- **Privacy**: Players can't see others' picks until they've submitted their own
- **Resubmission**: Players can resubmit picks as long as they haven't viewed others' picks
- **Email Confirmation**: Picks are emailed to the player on submission (optional, requires SMTP config)
- **Scoring**: Spread-based scoring clamped to [-15, +15] per game
- **Weekly Winners**: Determined by total points, tiebroken by winning picks count
- **Yearly Standings**: Full season tracking with qualification rules (4+ picks in weeks 17-18)
- **Weekly Prize Race**: Track weekly win accumulation with multi-level tiebreaking
- **Prize Pool**: Track entry fees, calculate prize distribution (2/3 yearly, 1/3 weekly, refunds for winners)

## Scoring Rules

- Points = (actual margin - spread), from the picked team's perspective, clamped to [-15, +15]
- A "winning pick" has strictly positive points (zero does not count)
- Need 4+ picks per week to be eligible for weekly prize
- Need 4+ picks in the last two weeks of the season to qualify for yearly prize
- Weekly winner tiebreaker: most winning picks among tied players
- Weekly prize winner tiebreakers: total wins, then winning picks in win weeks, then latest unique win
- Yearly prize tiebreaker: weekly competition performance

## Prize Distribution

- Each winner gets their entry fee refunded
- Yearly winners split 2/3 of the remaining entry fees
- Weekly winners split 1/3 of the remaining entry fees
- Example with 8 players at $30 ($240 pool): yearly winner gets $120, weekly winner gets $60
- If the same player wins both: $30 refund + $120 + $60 = $210

## Environment Variables (all optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | dev key (change in production) |
| `ODDS_API_KEY` | [The Odds API](https://the-odds-api.com) key for spreads | falls back to ESPN |
| `MAIL_SERVER` | SMTP server for email confirmations | disabled |
| `MAIL_PORT` | SMTP port | 587 |
| `MAIL_USERNAME` | SMTP username | |
| `MAIL_PASSWORD` | SMTP password | |
| `MAIL_DEFAULT_SENDER` | From address | noreply@pickem.local |

## Running Tests

```bash
python test_rules.py
```

Runs 49 automated tests covering all scoring rules from the specification.
