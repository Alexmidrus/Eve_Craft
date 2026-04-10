from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from iph2.shared.paths import package_root, project_root, src_root


@dataclass(frozen=True, slots=True)
class AppPaths:
    project_root: Path
    src_root: Path
    package_root: Path
    runtime_dir: Path
    databases_dir: Path
    downloads_dir: Path
    temporary_dir: Path
    ui_design_dir: Path
    main_window_ui: Path
    startup_splash_ui: Path
    sde_update_dialog_ui: Path
    icon_file: Path
    logs_dir: Path
    app_database_path: Path
    sde_database_path: Path
    settings_path: Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    application_name: str
    organization_name: str
    paths: AppPaths


def load_app_config() -> AppConfig:
    app_name = "IPH2"
    root = project_root()
    runtime_dir = root / "runtime"
    databases_dir = runtime_dir / "databases"
    downloads_dir = runtime_dir / "downloads"
    temporary_dir = runtime_dir / "tmp"
    logs_dir = runtime_dir / "logs"

    for path in (runtime_dir, databases_dir, downloads_dir, temporary_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    paths = AppPaths(
        project_root=root,
        src_root=src_root(),
        package_root=package_root(),
        runtime_dir=runtime_dir,
        databases_dir=databases_dir,
        downloads_dir=downloads_dir,
        temporary_dir=temporary_dir,
        ui_design_dir=root / "Ui_design",
        main_window_ui=root / "Ui_design" / "MainWindow.ui",
        startup_splash_ui=root / "Ui_design" / "StartupSplash.ui",
        sde_update_dialog_ui=root / "Ui_design" / "SdeUpdateDialog.ui",
        icon_file=root / "Ui_design" / "industry.svg",
        logs_dir=logs_dir,
        app_database_path=databases_dir / "app.sqlite3",
        sde_database_path=databases_dir / "sde.sqlite3",
        settings_path=runtime_dir / "settings.json",
    )
    return AppConfig(
        application_name=app_name,
        organization_name=app_name,
        paths=paths,
    )
