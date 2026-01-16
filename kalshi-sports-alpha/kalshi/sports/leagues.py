"""League definitions and configuration."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LeagueCode(Enum):
    """Supported league codes."""
    NFL = "NFL"
    NBA = "NBA"
    MLB = "MLB"
    NHL = "NHL"
    NCAAF = "NCAAF"
    NCAAB = "NCAAB"
    MLS = "MLS"
    EPL = "EPL"


@dataclass
class League:
    """League configuration and metadata."""

    code: LeagueCode
    name: str
    kalshi_series: str  # Kalshi series ticker pattern
    typical_game_duration_minutes: int
    has_overtime: bool = True
    has_live_markets: bool = False

    # Seasonality
    season_start_month: Optional[int] = None
    season_end_month: Optional[int] = None

    @property
    def is_american(self) -> bool:
        """Check if this is an American league."""
        return self.code in {
            LeagueCode.NFL,
            LeagueCode.NBA,
            LeagueCode.MLB,
            LeagueCode.NHL,
            LeagueCode.NCAAF,
            LeagueCode.NCAAB,
            LeagueCode.MLS,
        }


# Supported leagues with their configurations
SUPPORTED_LEAGUES: dict[LeagueCode, League] = {
    LeagueCode.NFL: League(
        code=LeagueCode.NFL,
        name="National Football League",
        kalshi_series="NFL",
        typical_game_duration_minutes=180,
        has_overtime=True,
        has_live_markets=True,
        season_start_month=9,
        season_end_month=2,
    ),
    LeagueCode.NBA: League(
        code=LeagueCode.NBA,
        name="National Basketball Association",
        kalshi_series="NBA",
        typical_game_duration_minutes=150,
        has_overtime=True,
        has_live_markets=True,
        season_start_month=10,
        season_end_month=6,
    ),
    LeagueCode.MLB: League(
        code=LeagueCode.MLB,
        name="Major League Baseball",
        kalshi_series="MLB",
        typical_game_duration_minutes=180,
        has_overtime=True,  # Extra innings
        has_live_markets=True,
        season_start_month=3,
        season_end_month=10,
    ),
    LeagueCode.NHL: League(
        code=LeagueCode.NHL,
        name="National Hockey League",
        kalshi_series="NHL",
        typical_game_duration_minutes=150,
        has_overtime=True,
        has_live_markets=False,
        season_start_month=10,
        season_end_month=6,
    ),
    LeagueCode.NCAAF: League(
        code=LeagueCode.NCAAF,
        name="NCAA Football",
        kalshi_series="NCAAF",
        typical_game_duration_minutes=210,
        has_overtime=True,
        has_live_markets=False,
        season_start_month=8,
        season_end_month=1,
    ),
    LeagueCode.NCAAB: League(
        code=LeagueCode.NCAAB,
        name="NCAA Basketball",
        kalshi_series="NCAAB",
        typical_game_duration_minutes=120,
        has_overtime=True,
        has_live_markets=False,
        season_start_month=11,
        season_end_month=4,
    ),
}


def get_league(code: str) -> Optional[League]:
    """Get league by code string."""
    try:
        league_code = LeagueCode(code.upper())
        return SUPPORTED_LEAGUES.get(league_code)
    except ValueError:
        return None


def is_league_in_season(league: League, month: int) -> bool:
    """Check if league is currently in season."""
    if league.season_start_month is None or league.season_end_month is None:
        return True

    start = league.season_start_month
    end = league.season_end_month

    if start <= end:
        return start <= month <= end
    else:
        # Season spans year boundary (e.g., NFL Sep-Feb)
        return month >= start or month <= end

