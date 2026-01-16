"""Data persistence - disk and database writers."""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from kalshi.models import MarketSnapshot


logger = logging.getLogger(__name__)


class DataWriter(ABC):
    """Abstract base class for data writers."""

    @abstractmethod
    def write(self, data: Any, path: str) -> None:
        """Write data to storage."""
        pass

    @abstractmethod
    def read(self, path: str) -> Any:
        """Read data from storage."""
        pass


class JsonWriter(DataWriter):
    """JSON file writer for snapshots and raw data."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, data: Any, path: str) -> None:
        """Write data as JSON."""
        full_path = self.base_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        with open(full_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.debug(f"Wrote JSON to {full_path}")

    def read(self, path: str) -> Any:
        """Read JSON data."""
        full_path = self.base_dir / path

        with open(full_path, "r") as f:
            return json.load(f)

    def write_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Write a market snapshot with organized path."""
        date_str = snapshot.snapshot_time.strftime("%Y-%m-%d")
        time_str = snapshot.snapshot_time.strftime("%H%M%S")

        path = f"{snapshot.league}/{date_str}/{snapshot.market_id}_{time_str}.json"
        self.write(snapshot.to_dict(), path)


class ParquetWriter(DataWriter):
    """Parquet file writer for efficient columnar storage."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, data: Any, path: str) -> None:
        """Write data as Parquet."""
        # Requires pandas and pyarrow
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for ParquetWriter")

        full_path = self.base_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            df = data

        df.to_parquet(full_path, index=False)
        logger.debug(f"Wrote Parquet to {full_path}")

    def read(self, path: str) -> Any:
        """Read Parquet data."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for ParquetWriter")

        full_path = self.base_dir / path
        return pd.read_parquet(full_path)

    def write_snapshots(
        self,
        snapshots: list[MarketSnapshot],
        partition_by: str = "league"
    ) -> None:
        """Write multiple snapshots with partitioning."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for ParquetWriter")

        records = [s.to_dict() for s in snapshots]
        df = pd.DataFrame(records)

        if partition_by and partition_by in df.columns:
            for value, group in df.groupby(partition_by):
                path = f"{partition_by}={value}/snapshots.parquet"
                self.write(group, path)
        else:
            self.write(df, "snapshots.parquet")


class SnapshotStore:
    """High-level interface for snapshot storage."""

    def __init__(
        self,
        raw_dir: Path,
        normalized_dir: Path,
        writer_class: type = JsonWriter
    ):
        self.raw_writer = writer_class(raw_dir)
        self.normalized_writer = writer_class(normalized_dir)

    def store_raw(self, data: dict, source: str) -> None:
        """Store raw API response."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{source}/{timestamp}.json"
        self.raw_writer.write(data, path)

    def store_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Store normalized snapshot."""
        if isinstance(self.normalized_writer, JsonWriter):
            self.normalized_writer.write_snapshot(snapshot)
        else:
            self.normalized_writer.write(snapshot.to_dict(), f"{snapshot.market_id}.json")

