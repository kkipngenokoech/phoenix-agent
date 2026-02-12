"""Phoenix Agent configuration - Pydantic-based with environment variable support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class LLMConfig(BaseModel):
    provider: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "anthropic"))
    model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929"))
    temperature: float = 0.0
    max_tokens: int = 4096
    base_url: Optional[str] = Field(default_factory=lambda: os.getenv("LLM_BASE_URL"))
    api_key: Optional[str] = Field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))


class RedisConfig(BaseModel):
    url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    session_ttl: int = 86400  # 24 hours


class PostgresConfig(BaseModel):
    url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://phoenix:phoenix@localhost:5432/phoenix",
        )
    )
    pool_size: int = 5


class Neo4jConfig(BaseModel):
    uri: str = Field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = Field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = Field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "phoenix123"))


class AgentConfig(BaseModel):
    max_iterations: int = 50
    max_retries: int = 3
    tool_timeout_seconds: int = 300  # 5 minutes
    high_risk_threshold: float = 7.0
    medium_risk_threshold: float = 4.0
    review_timeout: int = 3600  # 1 hour for user to approve/reject diffs


class PhoenixConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    sample_project_path: str = Field(
        default_factory=lambda: os.getenv("SAMPLE_PROJECT_PATH", "./sample_project")
    )
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @classmethod
    def from_env(cls) -> PhoenixConfig:
        return cls()
