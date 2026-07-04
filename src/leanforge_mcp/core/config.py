"""Config loader -- reads config.toml into typed dataclasses."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LeanConfig:
    # We invoke `lake env lean <file>`, not `lean` directly, so Mathlib resolves.
    lake_path: str = r"C:\Users\sandr\.elan\bin\lake.exe"
    # Lake project dir with Mathlib dependency + cached oleans (one-time setup).
    workspace_dir: str = r"D:\Dev\repos\leanforge-mcp\workspace\leanforge_workspace"
    compile_timeout: int = 120
    # Cap concurrent Lean processes -- each loads Mathlib, uses GBs of RAM.
    max_concurrent_compiles: int = 4
    retain_workspace: bool = False


@dataclass
class DatabaseConfig:
    path: str = r"D:\Dev\repos\leanforge-mcp\data\jobs.db"


@dataclass
class LLMTierConfig:
    provider: str = "ollama"
    model: str = "deepseek-prover-v2:7b"
    base_url: str = "http://localhost:11434/v1"
    api_key_env: str = ""
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class LLMConfig:
    tier1: LLMTierConfig = field(default_factory=LLMTierConfig)
    tier2: LLMTierConfig = field(
        default_factory=lambda: LLMTierConfig(
            provider="openai_compat",
            model="deepseek/deepseek-v4-flash",
            base_url="https://api.deepseek.com/v1",
            api_key_env="DEEPSEEK_API_KEY",
            max_tokens=4096,
        )
    )
    tier3: LLMTierConfig = field(
        default_factory=lambda: LLMTierConfig(
            provider="anthropic",
            model="claude-fable-5",
            api_key_env="ANTHROPIC_API_KEY",
            max_tokens=8192,
            temperature=1.0,
        )
    )


@dataclass
class AgentConfig:
    parallel_agents: int = 4
    max_turns: int = 100
    escalate_to_tier2_after: int = 20
    escalate_to_tier3_after: int = 60


@dataclass
class ServerConfig:
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class LoggingConfig:
    level: str = "INFO"
    log_file: str = r"D:\Dev\repos\leanforge-mcp\logs\leanforge.log"


@dataclass
class Config:
    lean: LeanConfig = field(default_factory=LeanConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _from_dict(cls, data: dict):
    """Recursively populate a dataclass from a dict."""
    import dataclasses

    if not dataclasses.is_dataclass(cls):
        return data
    kwargs = {}
    for f in dataclasses.fields(cls):
        if f.name in data:
            val = data[f.name]
            if dataclasses.is_dataclass(f.type) or (
                isinstance(f.type, type) and dataclasses.is_dataclass(f.type)
            ):
                kwargs[f.name] = _from_dict(f.type, val)
            else:
                kwargs[f.name] = val
    return cls(**kwargs)


def load_config(path: Path) -> Config:
    with path.open("rb") as f:
        raw = tomllib.load(f)

    config = Config()

    if "lean" in raw:
        config.lean = LeanConfig(
            **{k: v for k, v in raw["lean"].items() if k in LeanConfig.__dataclass_fields__}
        )
    if "database" in raw:
        config.database = DatabaseConfig(**raw["database"])
    if "agent" in raw:
        config.agent = AgentConfig(**raw["agent"])
    if "server" in raw:
        config.server = ServerConfig(**raw["server"])
    if "logging" in raw:
        config.logging = LoggingConfig(**raw["logging"])
    if "llm" in raw:
        llm_raw = raw["llm"]
        if "tier1" in llm_raw:
            config.llm.tier1 = LLMTierConfig(**llm_raw["tier1"])
        if "tier2" in llm_raw:
            config.llm.tier2 = LLMTierConfig(**llm_raw["tier2"])
        if "tier3" in llm_raw:
            config.llm.tier3 = LLMTierConfig(**llm_raw["tier3"])

    return config
