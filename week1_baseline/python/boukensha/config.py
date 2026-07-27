"""
Step 0 — Configuration

Python port of `Boukensha::Config`.

Single source of truth for all settings. Loads a config directory that stores
secrets, prompts, sessions (logs), and a settings file.

  - Default config dir:  ~/.boukensha
  - Override with env var: BOUKENSHA_DIR
  - Secrets from:          <dir>/.env
  - Settings from:         <dir>/settings.yaml  (or settings.json — see note)
  - Prompts in:            <dir>/prompts/
  - Sessions (logs) in:    <dir>/sessions/
"""

from __future__ import annotations

import os
from pathlib import Path

# YAML is optional. If pyyaml isn't installed we fall back to JSON so the
# framework stays runnable with zero third-party deps.
try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

import json


class Config:
    """Loads and exposes all configuration for the agent."""

    APP_NAME = "boukensha"
    ENV_OVERRIDE = "BOUKENSHA_DIR"

    def __init__(self, dir: str | os.PathLike | None = None):
        # Resolve the config directory: explicit arg > env var > default (~/.boukensha)
        if dir is not None:
            self.dir = Path(dir).expanduser().resolve()
        elif os.environ.get(self.ENV_OVERRIDE):
            self.dir = Path(os.environ[self.ENV_OVERRIDE]).expanduser().resolve()
        else:
            self.dir = (Path.home() / f".{self.APP_NAME}").resolve()

        # Make sure the directory structure exists.
        self._ensure_layout()

        # Load secrets (.env) into a dict, and merge into os.environ so the
        # rest of the app can read API keys the normal way.
        self.secrets = self._load_env(self.dir / ".env")

        # Load settings (yaml or json).
        self.settings = self._load_settings()

    # ---- Paths -----------------------------------------------------------

    @property
    def prompts_dir(self) -> Path:
        return self.dir / "prompts"

    @property
    def sessions_dir(self) -> Path:
        return self.dir / "sessions"

    @property
    def env_path(self) -> Path:
        return self.dir / ".env"

    @property
    def settings_path(self) -> Path:
        yaml_path = self.dir / "settings.yaml"
        json_path = self.dir / "settings.json"
        if yaml_path.exists():
            return yaml_path
        if json_path.exists():
            return json_path
        # Default to whichever format we can write.
        return yaml_path if _HAS_YAML else json_path

    # ---- Accessors -------------------------------------------------------

    def get(self, key: str, default=None):
        """Read a settings value (e.g. config.get('model'))."""
        return self.settings.get(key, default)

    def secret(self, key: str, default=None):
        """Read a secret from .env (e.g. config.secret('ANTHROPIC_API_KEY'))."""
        return self.secrets.get(key, default)

    # ---- Internals -------------------------------------------------------

    def _ensure_layout(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "prompts").mkdir(exist_ok=True)
        (self.dir / "sessions").mkdir(exist_ok=True)

    def _load_env(self, path: Path) -> dict[str, str]:
        """Minimal .env parser (KEY=VALUE per line, # comments, optional quotes)."""
        secrets: dict[str, str] = {}
        if not path.exists():
            return secrets
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            secrets[key] = val
            # Don't clobber a real env var if it's already set.
            os.environ.setdefault(key, val)
        return secrets

    def _load_settings(self) -> dict:
        path = self.settings_path
        if not path.exists():
            return {}
        text = path.read_text()
        if path.suffix == ".yaml" and _HAS_YAML:
            return yaml.safe_load(text) or {}
        if path.suffix == ".json":
            return json.loads(text) if text.strip() else {}
        # settings.yaml exists but no pyyaml — tell the user clearly.
        raise RuntimeError(
            f"{path} is YAML but pyyaml isn't installed. "
            f"Either `pip install pyyaml` or use settings.json instead."
        )

    def __repr__(self) -> str:
        return f"<Config dir={self.dir} settings_keys={list(self.settings)}>"


if __name__ == "__main__":
    # Quick smoke test.
    cfg = Config()
    print(cfg)
    print("config dir :", cfg.dir)
    print("prompts    :", cfg.prompts_dir)
    print("sessions   :", cfg.sessions_dir)
    print("settings   :", cfg.settings)
