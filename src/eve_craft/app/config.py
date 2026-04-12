from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eve_craft.shared.paths import package_root, project_root, src_root


@dataclass(frozen=True, slots=True)
class AppPaths:
    project_root: Path
    src_root: Path
    package_root: Path
    runtime_dir: Path
    resources_dir: Path
    sde_resources_dir: Path
    databases_dir: Path
    downloads_dir: Path
    temporary_dir: Path
    ui_design_dir: Path
    main_window_ui: Path
    startup_splash_ui: Path
    sde_update_dialog_ui: Path
    manage_accounts_ui: Path
    add_character_ui: Path
    icon_file: Path
    logs_dir: Path
    app_database_path: Path
    sde_database_path: Path
    types_images_dir: Path
    settings_path: Path


@dataclass(frozen=True, slots=True)
class AppConfig:
    application_name: str
    organization_name: str
    paths: AppPaths
    esi: "EsiConfig"


@dataclass(frozen=True, slots=True)
class EsiConfig:
    base_url: str
    sso_metadata_url: str
    default_callback_url: str
    compatibility_date: str
    user_agent: str
    request_timeout_seconds: int
    metadata_cache_ttl_seconds: int
    token_refresh_skew_seconds: int
    x_pages_expiry_safety_window_seconds: int


def _resolve_esi_compatibility_date() -> str:
    configured = os.environ.get("EVE_CRAFT_ESI_COMPATIBILITY_DATE")
    if configured:
        return configured

    resolved = datetime.now(timezone.utc) - timedelta(hours=11)
    return resolved.date().isoformat()


def _resolve_esi_user_agent(application_name: str) -> str:
    configured = os.environ.get("EVE_CRAFT_ESI_USER_AGENT")
    if configured:
        return configured

    normalized_name = application_name.replace(" ", "")
    return f"{normalized_name}/dev (desktop app)"


def load_app_config() -> AppConfig:
    app_name = "Eve Craft"
    root = project_root()
    runtime_dir = root / "runtime"
    resources_dir = runtime_dir / "resources"
    sde_resources_dir = resources_dir / "sde"
    databases_dir = runtime_dir / "databases"
    downloads_dir = runtime_dir / "downloads"
    temporary_dir = runtime_dir / "tmp"
    logs_dir = runtime_dir / "logs"

    for path in (runtime_dir, resources_dir, sde_resources_dir, databases_dir, downloads_dir, temporary_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    paths = AppPaths(
        project_root=root,
        src_root=src_root(),
        package_root=package_root(),
        runtime_dir=runtime_dir,
        resources_dir=resources_dir,
        sde_resources_dir=sde_resources_dir,
        databases_dir=databases_dir,
        downloads_dir=downloads_dir,
        temporary_dir=temporary_dir,
        ui_design_dir=root / "Ui_design",
        main_window_ui=root / "Ui_design" / "MainWindow.ui",
        startup_splash_ui=root / "Ui_design" / "StartupSplash.ui",
        sde_update_dialog_ui=root / "Ui_design" / "SdeUpdateDialog.ui",
        manage_accounts_ui=root / "Ui_design" / "ManageAccounts.ui",
        add_character_ui=root / "Ui_design" / "AddCharacter.ui",
        icon_file=root / "Ui_design" / "industry.svg",
        logs_dir=logs_dir,
        app_database_path=databases_dir / "app.sqlite3",
        sde_database_path=databases_dir / "sde.sqlite3",
        types_images_dir=sde_resources_dir / "types",
        settings_path=runtime_dir / "settings.json",
    )
    return AppConfig(
        application_name=app_name,
        organization_name=app_name,
        paths=paths,
        esi=EsiConfig(
            base_url=os.environ.get("EVE_CRAFT_ESI_BASE_URL", "https://esi.evetech.net/latest"),
            sso_metadata_url=os.environ.get(
                "EVE_CRAFT_ESI_SSO_METADATA_URL",
                "https://login.eveonline.com/.well-known/oauth-authorization-server",
            ),
            default_callback_url=os.environ.get(
                "EVE_CRAFT_ESI_CALLBACK_URL",
                "http://127.0.0.1:8080/callback",
            ),
            compatibility_date=_resolve_esi_compatibility_date(),
            user_agent=_resolve_esi_user_agent(app_name),
            request_timeout_seconds=int(os.environ.get("EVE_CRAFT_ESI_TIMEOUT_SECONDS", "30")),
            metadata_cache_ttl_seconds=int(os.environ.get("EVE_CRAFT_ESI_METADATA_CACHE_TTL_SECONDS", "300")),
            token_refresh_skew_seconds=int(os.environ.get("EVE_CRAFT_ESI_TOKEN_REFRESH_SKEW_SECONDS", "60")),
            x_pages_expiry_safety_window_seconds=int(
                os.environ.get("EVE_CRAFT_ESI_X_PAGES_EXPIRY_SAFETY_WINDOW_SECONDS", "5")
            ),
        ),
    )


