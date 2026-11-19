"""Winston configuration management."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class WinstonSettings(BaseSettings):
    """Winston application settings.
    
    Configuration can be provided via environment variables prefixed with WINSTON_.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="WINSTON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Database
    database_url: PostgresDsn = Field(
        default="postgresql://winston:winston_dev@localhost:5432/winston",
        description="PostgreSQL connection URL",
    )
    
    # Directories
    data_dir: Path = Field(
        default=Path(".winston"),
        description="Root directory for Winston runtime data",
    )
    
    @property
    def artifacts_dir(self) -> Path:
        """Directory for immutable evidence artifacts."""
        return self.data_dir / "artifacts"
    
    @property
    def cache_dir(self) -> Path:
        """Directory for Git object cache."""
        return self.data_dir / "cache"
    
    @property
    def fixtures_dir(self) -> Path:
        """Directory for synthetic fixture repositories."""
        return self.data_dir / "fixtures"
    
    @property
    def exports_dir(self) -> Path:
        """Directory for export bundles."""
        return self.data_dir / "exports"
    
    # Profiles
    profiles_dir: Path = Field(
        default=Path("profiles"),
        description="Directory containing profile definitions",
    )
    
    registry_dir: Path = Field(
        default=Path("registry"),
        description="Directory containing repository registry",
    )
    
    # Active profile
    profile: str = Field(
        default="synthetic",
        description="Active profile name",
    )
    
    # Operation modes
    offline_mode: bool = Field(
        default=True,
        description="When true, block all live network adapters",
    )

    live_smoke: bool = Field(
        default=False,
        description="Opt-in live smoke (also requires WINSTON_LIVE_SMOKE=1)",
    )

    # Live smoke budgets (overridable by profile)
    live_smoke_max_dates: int = Field(
        default=3,
        description="Max business dates per live smoke run",
    )
    live_smoke_max_rows: int = Field(
        default=500,
        description="Max rows per live smoke query",
    )
    live_smoke_max_seconds: int = Field(
        default=60,
        description="Max seconds per live smoke run",
    )
    
    # Budgets
    max_repositories_per_investigation: int = Field(
        default=10,
        description="Maximum repositories to traverse per investigation",
    )
    
    max_files_per_repository: int = Field(
        default=100,
        description="Maximum files to read per repository",
    )
    
    max_bytes_per_file: int = Field(
        default=1_000_000,
        description="Maximum bytes to read per file",
    )
    
    # Output
    output_format: Literal["text", "json"] = Field(
        default="text",
        description="Default output format for CLI",
    )


def get_settings() -> WinstonSettings:
    """Get application settings singleton."""
    return WinstonSettings()
