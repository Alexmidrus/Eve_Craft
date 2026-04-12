from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from eve_craft.platform.db.models import AppBase


class EsiCacheRecord(AppBase):
    __tablename__ = "esi_cache_entries"

    cache_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    context_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagination_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_before: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_after: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_from_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EsiSyncStateRecord(AppBase):
    __tablename__ = "esi_sync_states"

    context_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    pagination_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    next_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_before: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_after: Mapped[str | None] = mapped_column(String(255), nullable=True)
    next_from_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_success_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
