from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from .schema import GrowSpec
from .validator import validate_spec

_ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


class SpecLoadError(Exception):
    pass


def _expand_env_vars(text: str) -> str:
    def replacer(m: re.Match) -> str:
        key = m.group(1)
        value = os.environ.get(key)
        if value is None:
            raise SpecLoadError(f"Environment variable ${{{key}}} is not set")
        return value

    return _ENV_VAR_RE.sub(replacer, text)


def load_spec(path: str | Path) -> GrowSpec:
    """Load, expand env vars, parse, and validate a GrowSpec YAML file."""
    raw = Path(path).read_text()
    try:
        expanded = _expand_env_vars(raw)
    except SpecLoadError:
        raise
    data = yaml.safe_load(expanded)
    try:
        spec = GrowSpec.model_validate(data)
    except ValidationError as e:
        raise SpecLoadError(f"Invalid spec at {path}:\n{e}") from e
    validate_spec(spec)
    return spec
