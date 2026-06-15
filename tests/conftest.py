import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _telegram_env(monkeypatch):
    # The reference spec interpolates these; set them so load_spec succeeds.
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def oyster_spec_path() -> Path:
    return FIXTURES / "oyster_fruiting.pyfarm.yaml"
