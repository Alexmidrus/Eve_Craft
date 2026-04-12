from __future__ import annotations

from datetime import timezone

from sqlalchemy import select

from eve_craft.platform.auth.domain.models import AuthenticatedCharacter
from eve_craft.platform.auth.infrastructure.models import AuthTokenRecord
from eve_craft.platform.db.session import DatabaseManager


def _serialize_values(values: tuple[str, ...]) -> str:
    return " ".join(values)


def _deserialize_values(serialized: str) -> tuple[str, ...]:
    if not serialized.strip():
        return ()

    return tuple(value for value in serialized.split(" ") if value)


def _ensure_utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class AuthTokenRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def save(self, token: AuthenticatedCharacter) -> AuthenticatedCharacter:
        with self._database.create_session() as session:
            record = session.scalar(
                select(AuthTokenRecord).where(AuthTokenRecord.character_id == token.character_id).limit(1)
            )
            if record is None:
                record = AuthTokenRecord(
                    character_id=token.character_id,
                    character_name=token.character_name,
                    subject=token.subject,
                    owner_hash=token.owner_hash,
                    scopes=_serialize_values(token.scopes),
                    audience=_serialize_values(token.audience),
                    access_token=token.access_token,
                    refresh_token=token.refresh_token,
                    token_type=token.token_type,
                    expires_at=token.expires_at,
                    issued_at=token.issued_at,
                    last_verified_at=token.last_verified_at,
                )
                session.add(record)
            else:
                record.character_name = token.character_name
                record.subject = token.subject
                record.owner_hash = token.owner_hash
                record.scopes = _serialize_values(token.scopes)
                record.audience = _serialize_values(token.audience)
                record.access_token = token.access_token
                record.refresh_token = token.refresh_token
                record.token_type = token.token_type
                record.expires_at = token.expires_at
                record.issued_at = token.issued_at
                record.last_verified_at = token.last_verified_at

            session.commit()

        return token

    def get(self, character_id: int) -> AuthenticatedCharacter | None:
        with self._database.create_session() as session:
            record = session.scalar(
                select(AuthTokenRecord).where(AuthTokenRecord.character_id == character_id).limit(1)
            )

        if record is None:
            return None

        return self._to_domain(record)

    def list_all(self) -> tuple[AuthenticatedCharacter, ...]:
        with self._database.create_session() as session:
            records = tuple(session.scalars(select(AuthTokenRecord).order_by(AuthTokenRecord.character_name)).all())

        return tuple(self._to_domain(record) for record in records)

    def delete(self, character_id: int) -> None:
        with self._database.create_session() as session:
            record = session.scalar(
                select(AuthTokenRecord).where(AuthTokenRecord.character_id == character_id).limit(1)
            )
            if record is None:
                return

            session.delete(record)
            session.commit()

    def count(self) -> int:
        return len(self.list_all())

    @staticmethod
    def _to_domain(record: AuthTokenRecord) -> AuthenticatedCharacter:
        return AuthenticatedCharacter(
            character_id=record.character_id,
            character_name=record.character_name,
            subject=record.subject,
            owner_hash=record.owner_hash,
            scopes=_deserialize_values(record.scopes),
            audience=_deserialize_values(record.audience),
            access_token=record.access_token,
            refresh_token=record.refresh_token,
            token_type=record.token_type,
            expires_at=_ensure_utc(record.expires_at),
            issued_at=_ensure_utc(record.issued_at),
            last_verified_at=_ensure_utc(record.last_verified_at),
        )
