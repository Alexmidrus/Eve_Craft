from __future__ import annotations

from eve_craft.app.environment import load_project_dotenv
from eve_craft.app.bootstrap import bootstrap_application


def main() -> int:
    load_project_dotenv(override=False)
    return bootstrap_application()

