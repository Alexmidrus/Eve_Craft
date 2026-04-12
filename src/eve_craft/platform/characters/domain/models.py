from __future__ import annotations

from dataclasses import dataclass

from eve_craft.platform.auth.domain.models import AuthenticatedCharacter


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    character_id: int
    character_name: str
    corporation_id: int | None = None
    alliance_id: int | None = None


@dataclass(frozen=True, slots=True)
class ManagedCharacter:
    authorization: AuthenticatedCharacter
    corporation_id: int | None = None
    alliance_id: int | None = None
    is_default: bool = False

    @property
    def access_token(self) -> str:
        return self.authorization.access_token

    @property
    def character_id(self) -> int:
        return self.authorization.character_id

    @property
    def character_name(self) -> str:
        return self.authorization.character_name

    @property
    def expires_at(self):
        return self.authorization.expires_at

    @property
    def refresh_token(self) -> str | None:
        return self.authorization.refresh_token

    @property
    def scopes(self) -> tuple[str, ...]:
        return self.authorization.scopes
