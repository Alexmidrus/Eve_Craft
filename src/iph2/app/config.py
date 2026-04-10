from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from iph2.shared.paths import default_user_data_dir, package_root, project_root, src_root


@dataclass(frozen=True, slots=True)
class AppPaths:
    project_root: Path
    src_root: Path
    package_root: Path
    ui_design_dir: Path
    main_window_ui: Path
    icon_file: Path
    user_data_dir: Path
    logs_dir: Path
    database_path: Path
    settings_path: Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    application_name: str
    organization_name: str
    paths: AppPaths


def load_app_config() -> AppConfig:
    app_name = "IPH2"
    user_data_dir = default_user_data_dir(app_name)
    logs_dir = user_data_dir / "logs"

    user_data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    paths = AppPaths(
        project_root=project_root(),
        src_root=src_root(),
        package_root=package_root(),
        ui_design_dir=project_root() / "Ui_design",
        main_window_ui=project_root() / "Ui_design" / "MainWindow.ui",
        icon_file=project_root() / "Ui_design" / "industry.svg",
        user_data_dir=user_data_dir,
        logs_dir=logs_dir,
        database_path=user_data_dir / "iph2.sqlite3",
        settings_path=user_data_dir / "settings.json",
    )
    return AppConfig(
        application_name=app_name,
        organization_name=app_name,
        paths=paths,
    )
