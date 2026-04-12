from __future__ import annotations

from eve_craft.platform.auth.domain.models import AuthenticatedCharacter
from eve_craft.platform.auth.service import AuthService
from eve_craft.platform.characters.domain.models import CharacterProfile, ManagedCharacter
from eve_craft.platform.characters.infrastructure.repository import CharacterProfileRepository
from eve_craft.platform.characters.settings_keys import DEFAULT_CHARACTER_SETTING_KEY
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.domain.models import EsiOperationDescriptor
from eve_craft.platform.esi.domain.pagination import EsiAuthMode
from eve_craft.platform.esi.service import EsiService
from eve_craft.platform.settings.service import SettingsService

PUBLIC_CHARACTER_PROFILE_OPERATION = EsiOperationDescriptor(
    key="platform.characters.public_profile.v1",
    method="GET",
    path="/characters/{character_id}/",
    auth_mode=EsiAuthMode.PUBLIC,
)


class CharacterService:
    def __init__(
        self,
        *,
        auth: AuthService,
        esi: EsiService,
        settings: SettingsService,
        database: DatabaseManager,
    ) -> None:
        self._auth = auth
        self._esi = esi
        self._settings = settings
        self._profile_repository = CharacterProfileRepository(database)
        self._esi.register_operation(PUBLIC_CHARACTER_PROFILE_OPERATION)

    def list_managed_characters(self) -> tuple[ManagedCharacter, ...]:
        authorized_characters = self._auth.list_authorized_characters()
        default_character_id = self._normalize_default_character_id(authorized_characters)
        profiles = self._profile_repository.list_for_character_ids(
            character.character_id for character in authorized_characters
        )
        return tuple(
            self._build_managed_character(
                character,
                profiles.get(character.character_id),
                is_default=character.character_id == default_character_id,
            )
            for character in authorized_characters
        )

    def get_managed_character(self, character_id: int, *, sync_if_missing: bool = False) -> ManagedCharacter | None:
        authorized_character = self._find_authorized_character(character_id)
        if authorized_character is None:
            return None

        profile = self._profile_repository.get(character_id)
        if profile is None and sync_if_missing:
            profile = self.sync_character_profile(character_id)

        default_character_id = self._normalize_default_character_id(self._auth.list_authorized_characters())
        return self._build_managed_character(
            authorized_character,
            profile,
            is_default=character_id == default_character_id,
        )

    def handle_authorized_character(self, character: AuthenticatedCharacter) -> ManagedCharacter:
        self._normalize_default_character_id(self._auth.list_authorized_characters())
        profile = self.sync_character_profile(character.character_id, force_refresh=True)
        default_character_id = self._normalize_default_character_id(self._auth.list_authorized_characters())
        return self._build_managed_character(
            character,
            profile,
            is_default=character.character_id == default_character_id,
        )

    def refresh_character_data(self, character_id: int) -> ManagedCharacter:
        refreshed = self._auth.refresh_character(character_id)
        profile = self.sync_character_profile(character_id, force_refresh=True)
        default_character_id = self._normalize_default_character_id(self._auth.list_authorized_characters())
        return self._build_managed_character(
            refreshed,
            profile,
            is_default=character_id == default_character_id,
        )

    def revoke_character(self, character_id: int) -> None:
        self._auth.revoke_character(character_id)
        self._profile_repository.delete(character_id)
        self._normalize_default_character_id(self._auth.list_authorized_characters())

    def set_default_character(self, character_id: int) -> ManagedCharacter:
        managed_character = self.get_managed_character(character_id)
        if managed_character is None:
            raise RuntimeError(f"Character {character_id} is not authorized.")

        self._store_default_character_id(character_id)
        return ManagedCharacter(
            authorization=managed_character.authorization,
            corporation_id=managed_character.corporation_id,
            alliance_id=managed_character.alliance_id,
            is_default=True,
        )

    def get_default_character_id(self) -> int | None:
        return self._normalize_default_character_id(self._auth.list_authorized_characters())

    def sync_character_profile(self, character_id: int, *, force_refresh: bool = False) -> CharacterProfile:
        authorized_character = self._find_authorized_character(character_id)
        if authorized_character is None:
            raise RuntimeError(f"Character {character_id} is not authorized.")

        envelope = self._esi.execute(
            PUBLIC_CHARACTER_PROFILE_OPERATION,
            route_params={"character_id": character_id},
            force_refresh=force_refresh,
        )
        payload = envelope.payload
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"ESI character profile '{character_id}' returned an unexpected payload type: {type(payload).__name__}."
            )

        profile = CharacterProfile(
            character_id=character_id,
            character_name=str(payload.get("name") or authorized_character.character_name),
            corporation_id=self._parse_optional_int(payload.get("corporation_id")),
            alliance_id=self._parse_optional_int(payload.get("alliance_id")),
        )
        return self._profile_repository.save(profile)

    def describe_management(self) -> str:
        default_character_id = self.get_default_character_id()
        if default_character_id is None:
            return "Character management is available, but no default character is selected yet."

        return f"Character management is available. Default character id: {default_character_id}."

    def _find_authorized_character(self, character_id: int) -> AuthenticatedCharacter | None:
        return next(
            (character for character in self._auth.list_authorized_characters() if character.character_id == character_id),
            None,
        )

    def _normalize_default_character_id(self, authorized_characters: tuple[AuthenticatedCharacter, ...]) -> int | None:
        if not authorized_characters:
            if self._load_default_character_id() is not None:
                self._store_default_character_id(None)
            return None

        stored_character_id = self._load_default_character_id()
        authorized_ids = {character.character_id for character in authorized_characters}
        if stored_character_id in authorized_ids:
            return stored_character_id

        fallback_character_id = authorized_characters[0].character_id
        self._store_default_character_id(fallback_character_id)
        return fallback_character_id

    def _load_default_character_id(self) -> int | None:
        value = self._settings.get(DEFAULT_CHARACTER_SETTING_KEY)
        if value in (None, ""):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _store_default_character_id(self, character_id: int | None) -> None:
        self._settings.set(DEFAULT_CHARACTER_SETTING_KEY, character_id)

    @staticmethod
    def _build_managed_character(
        character: AuthenticatedCharacter,
        profile: CharacterProfile | None,
        *,
        is_default: bool,
    ) -> ManagedCharacter:
        return ManagedCharacter(
            authorization=character,
            corporation_id=profile.corporation_id if profile is not None else None,
            alliance_id=profile.alliance_id if profile is not None else None,
            is_default=is_default,
        )

    @staticmethod
    def _parse_optional_int(value: object) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
