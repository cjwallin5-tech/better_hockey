import os

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=hockey_stats")
SEASON_ID = int(os.environ.get("SEASON_ID", "20262027"))
GAME_TYPE = 2  # regular season

# The NHL moved to an 84-game schedule.
GAMES_PER_SEASON = 84


def regular_season_games(season_id):
    """Games in a season's regular schedule: 32 teams x 82 games / 2 = 1312 up to 2025-26, 32 x 84 / 2 = 1344 from 2026-27."""
    return 1344 if season_id >= 20262027 else 1312
RECENT_WINDOW = 10  # games used for the "last N" pace
RECENT_GOALIE_GAMES = 5  # goalies play far less often, so their "recent form" window is shorter

STATS_API = "https://api.nhle.com/stats/rest/en"
WEB_API = "https://api-web.nhle.com/v1"

# Password-reset email. With SMTP_HOST unset the reset link is printed to the API log instead (local dev only).
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:5173").rstrip("/")  # where reset links point
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", "Faceoff <no-reply@localhost>")

# Accounts allowed to open the Accuracy page (comma-separated emails, compared without case).
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "cjwallin5@gmail.com").split(",") if e.strip()}
