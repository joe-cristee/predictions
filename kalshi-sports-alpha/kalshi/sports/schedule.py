"""Game schedule handling and time normalization."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum


class KickoffWindow(Enum):
    """Defined time regimes relative to kickoff."""
    FAR = "far"              # T-24h to T-2h
    APPROACHING = "approaching"  # T-2h to T-10m
    IMMINENT = "imminent"    # T-10m to kickoff
    LIVE = "live"            # In-play


@dataclass
class GameSchedule:
    """Represents a scheduled game with timing information."""

    event_id: str
    league: str
    home_team: str
    away_team: str
    scheduled_start: datetime
    venue: Optional[str] = None

    # Status
    is_postponed: bool = False
    is_cancelled: bool = False
    actual_start: Optional[datetime] = None

    @property
    def kickoff_time(self) -> datetime:
        """Get the effective kickoff time."""
        return self.actual_start or self.scheduled_start

    def time_to_kickoff(self, now: Optional[datetime] = None) -> timedelta:
        """Calculate time until kickoff."""
        now = now or datetime.now(timezone.utc)
        return self.kickoff_time - now

    def seconds_to_kickoff(self, now: Optional[datetime] = None) -> int:
        """Calculate seconds until kickoff."""
        return int(self.time_to_kickoff(now).total_seconds())

    def get_kickoff_window(self, now: Optional[datetime] = None) -> KickoffWindow:
        """Determine current kickoff window regime."""
        seconds = self.seconds_to_kickoff(now)

        if seconds < 0:
            return KickoffWindow.LIVE
        elif seconds <= 600:  # 10 minutes
            return KickoffWindow.IMMINENT
        elif seconds <= 7200:  # 2 hours
            return KickoffWindow.APPROACHING
        else:
            return KickoffWindow.FAR


def normalize_game_time(
    time_str: str,
    timezone_str: str = "America/New_York"
) -> datetime:
    """
    Normalize a game time string to UTC datetime.

    Args:
        time_str: Time string in various formats
        timezone_str: Source timezone

    Returns:
        UTC datetime
    """
    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %I:%M %p",
        "%m/%d/%Y %I:%M %p",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(time_str, fmt)
            if dt.tzinfo is None:
                # Assume Eastern time for US sports
                # In production, use proper timezone library
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    raise ValueError(f"Unable to parse time string: {time_str}")


def get_window_for_seconds(seconds_to_kickoff: int) -> KickoffWindow:
    """Get kickoff window from seconds."""
    if seconds_to_kickoff < 0:
        return KickoffWindow.LIVE
    elif seconds_to_kickoff <= 600:
        return KickoffWindow.IMMINENT
    elif seconds_to_kickoff <= 7200:
        return KickoffWindow.APPROACHING
    else:
        return KickoffWindow.FAR


def is_primetime_slot(kickoff: datetime, league: str) -> bool:
    """
    Check if game is in a primetime slot.
    
    Primetime games typically have higher liquidity.
    """
    # Convert to Eastern for US sports
    hour = kickoff.hour  # Simplified - should use proper TZ conversion

    if league in ("NFL", "NCAAF"):
        # Sunday/Monday/Thursday night games
        weekday = kickoff.weekday()
        if weekday in (0, 3, 6) and hour >= 20:  # Mon, Thu, Sun evening
            return True
    elif league in ("NBA", "NHL"):
        # Late games on national TV
        if hour >= 19:
            return True
    elif league == "MLB":
        # Playoff games, Sunday night baseball
        if kickoff.weekday() == 6 and hour >= 19:
            return True

    return False

