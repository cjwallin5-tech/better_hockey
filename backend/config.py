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
