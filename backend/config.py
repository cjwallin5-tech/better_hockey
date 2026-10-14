import os

DATABASE_URL = os.environ.get("DATABASE_URL", "dbname=hockey_stats")
SEASON_ID = int(os.environ.get("SEASON_ID", "20262027"))
GAME_TYPE = 2  # regular season

# The NHL moved to an 84-game schedule.
GAMES_PER_SEASON = 84
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
SMTP_FROM = os.environ.get("SMTP_FROM", "NHL Stats <no-reply@localhost>")
