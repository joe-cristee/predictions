"""Sports metadata - teams, venues, season context."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Team:
    """Team information."""

    code: str  # e.g., "KC", "LAL"
    name: str  # e.g., "Chiefs", "Lakers"
    city: str  # e.g., "Kansas City", "Los Angeles"
    league: str
    conference: Optional[str] = None
    division: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Full team name."""
        return f"{self.city} {self.name}"

    @property
    def display_name(self) -> str:
        """Short display name."""
        return self.name


@dataclass
class Venue:
    """Venue information."""

    name: str
    city: str
    state: Optional[str] = None
    country: str = "USA"
    capacity: Optional[int] = None
    is_dome: bool = False
    surface: Optional[str] = None  # e.g., "grass", "turf"
    timezone: str = "America/New_York"

    @property
    def is_outdoor(self) -> bool:
        """Check if venue is outdoor."""
        return not self.is_dome


# Common team aliases for matching
TEAM_ALIASES: dict[str, str] = {
    # NFL
    "KC": "Kansas City Chiefs",
    "Chiefs": "Kansas City Chiefs",
    "BUF": "Buffalo Bills",
    "Bills": "Buffalo Bills",
    "SF": "San Francisco 49ers",
    "49ers": "San Francisco 49ers",
    "Niners": "San Francisco 49ers",
    # NBA
    "LAL": "Los Angeles Lakers",
    "Lakers": "Los Angeles Lakers",
    "BOS": "Boston Celtics",
    "Celtics": "Boston Celtics",
    "GSW": "Golden State Warriors",
    "Warriors": "Golden State Warriors",
    "Dubs": "Golden State Warriors",
    # Add more as needed
}


def normalize_team_name(name: str) -> str:
    """Normalize a team name to canonical form."""
    # Check aliases first
    normalized = TEAM_ALIASES.get(name)
    if normalized:
        return normalized

    # Check case-insensitive
    name_upper = name.upper()
    for alias, canonical in TEAM_ALIASES.items():
        if alias.upper() == name_upper:
            return canonical

    # Return as-is if no match
    return name


def extract_teams_from_title(title: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extract home and away teams from market title.
    
    Common formats:
    - "Team A vs Team B"
    - "Team A @ Team B"
    - "Team A at Team B"
    
    Returns:
        (away_team, home_team) tuple
    """
    # Try different separators
    separators = [" vs ", " @ ", " at ", " vs. "]

    for sep in separators:
        if sep in title.lower():
            parts = title.lower().split(sep.lower())
            if len(parts) == 2:
                away = parts[0].strip()
                home = parts[1].strip()
                return (normalize_team_name(away), normalize_team_name(home))

    return (None, None)

