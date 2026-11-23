"""The preview of a prepared batch: rows with class and reason, and both versions of a conflict."""

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.batches import BatchNotFound, UnitOfWork


@dataclass(frozen=True)
class PreviewRow:
    row_number: int
    row_class: str
    reason: str | None
    fields: dict[str, str | None]  # as the file said, kept as text
    existing: dict[str, Any] | None  # the stored incident, for a conflict with existing data
    differing_fields: list[str]
    repeated_in_file: list[int]


@dataclass(frozen=True)
class RowsPage:
    items: list[PreviewRow]
    page: int
    page_size: int
    total: int  # rows matching the filter
    totals_by_class: dict[str, int]  # the whole batch: nothing is cut off silently


class PreviewRepository(Protocol):
    def rows_page(
        self, batch_id: str, row_class: str | None, page: int, page_size: int
    ) -> RowsPage: ...

    def excluded_rows(self, batch_id: str) -> list[PreviewRow]: ...


class PreviewService:
    def __init__(self, uow: UnitOfWork, repository: PreviewRepository) -> None:
        self._uow = uow
        self._repository = repository

    def rows(
        self, owner: str, batch_id: str, row_class: str | None, page: int, page_size: int
    ) -> RowsPage:
        with self._uow() as tx:
            batch = tx.batches.get_for_owner(batch_id, owner)
        if batch is None or batch.state != "in_review":
            raise BatchNotFound(batch_id)  # not prepared yet, or not the user's
        return self._repository.rows_page(batch_id, row_class, page, page_size)

    def excluded(self, owner: str, batch_id: str) -> list[PreviewRow]:
        """Every row that will not be imported, with its reason, for the report."""
        with self._uow() as tx:
            batch = tx.batches.get_for_owner(batch_id, owner)
        if batch is None or batch.state != "in_review":
            raise BatchNotFound(batch_id)
        return self._repository.excluded_rows(batch_id)
