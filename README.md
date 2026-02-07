# NFL Pick'em Pool

A web application for running an NFL pick'em pool with spread-based scoring.

## Quick Start

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Set environment variables
export ODDS_API_KEY=your_key_here  # Get free at https://the-odds-api.com
export SECRET_KEY=your-secret-key

# Run the app
python run.py
```

Visit http://localhost:5050 in your browser.

## Default Admin Login

- **Username:** `admin`
- **Password:** `admin123`

Change the admin password after first login.

## Features

- **User Management**: Admin can add/deactivate users and reset passwords
- **Season/Week Management**: Create NFL seasons with 18 weeks, manage game schedules
- **Odds Fetching**: Auto-fetch spreads from ESPN and The Odds API
- **Pick Submission**: Players pick games against the spread
- **Privacy**: Players can't see others' picks until they've submitted their own
- **Scoring**: Spread-based scoring clamped to [-15, +15] per game
- **Weekly Winners**: Determined by total points, tiebroken by winning picks
- **Yearly Standings**: Full season tracking with qualification rules
- **Weekly Prize Race**: Track weekly win accumulation across the season

## Scoring Rules

- Points = (actual margin) - (spread), from the picked team's perspective
- Clamped to [-15, +15]
- A "winning pick" has positive points
- Need 4+ picks per week to be eligible for weekly prize
- Must make 4+ picks in last two weeks to qualify for yearly prize

## API Keys

For spread data, you can get a free API key from [The Odds API](https://the-odds-api.com).
Set it as the `ODDS_API_KEY` environment variable. Without it, the app falls back to ESPN data.
