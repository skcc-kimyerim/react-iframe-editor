import os
import sys
from pathlib import Path
import logging
import pytest


@pytest.fixture(autouse=True, scope="session")
def _set_test_env() -> None:
    os.environ.setdefault("FIGMA_API_TOKEN", "test-token")
    # Ensure app/ is on sys.path for module imports like `figma2code.*`
    root = Path(__file__).resolve().parents[1]
    app_dir = root / "app"
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))


@pytest.fixture(autouse=True)
def _silence_logging() -> None:
    logging.getLogger().setLevel(logging.WARNING)


@pytest.fixture
def fake_figma_url() -> str:
    return "https://www.figma.com/design/abcd/Example?node-id=1-2"
