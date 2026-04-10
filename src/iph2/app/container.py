from __future__ import annotations

from dataclasses import dataclass

from iph2.app.config import AppConfig
from iph2.app.module_registry import ModuleRegistry
from iph2.platform.auth.service import AuthService
from iph2.platform.characters.service import CharacterService
from iph2.platform.db.service import AppDatabaseService
from iph2.platform.db.session import DatabaseManager
from iph2.platform.esi.service import EsiService
from iph2.platform.sde.service import SdeService
from iph2.platform.settings.service import SettingsService


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
