from __future__ import annotations

from dataclasses import dataclass

from eve_craft.app.config import AppConfig
from eve_craft.app.module_registry import ModuleRegistry
from eve_craft.platform.auth.service import AuthService
from eve_craft.platform.characters.service import CharacterService
from eve_craft.platform.db.service import AppDatabaseService
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.service import EsiService
from eve_craft.platform.sde.service import SdeService
from eve_craft.platform.settings.service import SettingsService


@dataclass(slots=True)
class AppContainer:
    config: AppConfig
    module_registry: ModuleRegistry
    app_database: AppDatabaseService
    settings: SettingsService
    auth: AuthService
    esi: EsiService
    sde: SdeService
    characters: CharacterService


def build_container(config: AppConfig, module_registry: ModuleRegistry) -> AppContainer:
    database = DatabaseManager(config.paths.app_database_path)
    app_database = AppDatabaseService(database, application_name=config.application_name)
    settings = SettingsService(config.paths.settings_path)
    auth = AuthService()
    esi = EsiService()
    sde = SdeService(config)
    characters = CharacterService()

    return AppContainer(
        config=config,
        module_registry=module_registry,
        app_database=app_database,
        settings=settings,
        auth=auth,
        esi=esi,
        sde=sde,
        characters=characters,
    )

