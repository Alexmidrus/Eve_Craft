from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select

from eve_craft.platform.characters.domain.models import CharacterProfile
from eve_craft.platform.characters.infrastructure.models import CharacterProfileRecord
from eve_craft.platform.db.session import DatabaseManager


class CharacterProfileRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def save(self, profile: CharacterProfile) -> CharacterProfile:
        with self._database.create_session() as session:
            record = session.scalar(
                select(CharacterProfileRecord).where(CharacterProfileRecord.character_id == profile.character_id).limit(1)
            )
            if record is None:
                record = CharacterProfileRecord(
                    character_id=profile.character_id,
                    character_name=profile.character_name,
                    corporation_id=profile.corporation_id,
                    alliance_id=profile.alliance_id,
                )
                session.add(record)
            else:
                record.character_name = profile.character_name
                record.corporation_id = profile.corporation_id
                record.alliance_id = profile.alliance_id

            session.commit()

        return profile

    def get(self, character_id: int) -> CharacterProfile | None:
        with self._database.create_session() as session:
            record = session.scalar(
                select(CharacterProfileRecord).where(CharacterProfileRecord.character_id == character_id).limit(1)
            )

        if record is None:
            return None

        return self._to_domain(record)

    def list_for_character_ids(self, character_ids: Iterable[int]) -> dict[int, CharacterProfile]:
        normalized_ids = tuple(dict.fromkeys(int(character_id) for character_id in character_ids))
        if not normalized_ids:
            return {}

        with self._database.create_session() as session:
            records = tuple(
                session.scalars(
                    select(CharacterProfileRecord).where(CharacterProfileRecord.character_id.in_(normalized_ids))
                ).all()
            )

        return {record.character_id: self._to_domain(record) for record in records}

    def delete(self, character_id: int) -> None:
        with self._database.create_session() as session:
            record = session.scalar(
                select(CharacterProfileRecord).where(CharacterProfileRecord.character_id == character_id).limit(1)
            )
            if record is None:
                return

            session.delete(record)
            session.commit()

    @staticmethod
    def _to_domain(record: CharacterProfileRecord) -> CharacterProfile:
        return CharacterProfile(
            character_id=record.character_id,
            character_name=record.character_name,
            corporation_id=record.corporation_id,
            alliance_id=record.alliance_id,
        )
