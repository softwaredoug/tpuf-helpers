from collections.abc import Callable, Iterable, Iterator, Mapping
from importlib import import_module
from itertools import islice
from typing import Any

from turbopuffer import NotFoundError
from turbopuffer.types import (
    DistanceMetric,
    IncludeAttributesParam,
    NamespaceSummary,
    Row,
)


def ls(
    client,
    *,
    prefix: str | None = None,
    page_size: int | None = None,
) -> Iterator[NamespaceSummary]:
    """Iterate through namespaces, optionally filtered by prefix.

    The API's paginated iterator is consumed lazily, so this yields namespaces
    across all pages without loading the full listing into memory.
    """
    options: dict[str, Any] = {}
    if prefix is not None:
        options["prefix"] = prefix
    if page_size is not None:
        options["page_size"] = page_size

    yield from client.namespaces(**options)


def fetch(ns, doc_id: str) -> Row | None:
    """Fetch a document by id."""
    try:
        result = ns.query(
            filters=("id", "Eq", doc_id),
            rank_by=("id", "asc"),
            limit=1,
            include_attributes=True,
        )

        return result.rows[0] if result.rows else None
    except NotFoundError:
        return None


def exists(ns, doc_id: str) -> bool:
    """Check if document exists."""
    return fetch(ns, doc_id) is not None


def fetch_all(
    ns,
    include_attributes: IncludeAttributesParam = True,
    *,
    page_size: int = 100,
    limit: int | None = None,
) -> Iterator[Row]:
    """Iterate through namespace documents in ID order, optionally limited.

    When limited, iteration stops after the current page, so it may yield up
    to one page more than the requested limit.
    """
    if not 1 <= page_size <= 10_000:
        raise ValueError("page_size must be between 1 and 10000")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if limit == 0:
        return

    last_id = None
    documents_fetched = 0
    while True:
        query_options: dict[str, Any] = {
            "rank_by": ("id", "asc"),
            "limit": page_size,
            "include_attributes": include_attributes,
        }
        if last_id is not None:
            query_options["filters"] = ("id", "Gt", last_id)

        try:
            result = ns.query(**query_options)
        except NotFoundError:
            return

        rows = result.rows
        yield from rows
        documents_fetched += len(rows)
        if limit is not None and documents_fetched >= limit:
            return
        if len(rows) < page_size:
            return
        last_id = rows[-1].id


def count(ns):
    """Count documents in namespace."""
    try:
        return ns.query(
            aggregate_by={"count": ("Count",)}
        ).aggregations["count"]
    except NotFoundError:
        return 0


def drop(ns):
    """Drop the namespace."""
    try:
        ns.delete_all()
    except NotFoundError:
        pass


def no_op_enrich(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a batch unchanged when no enrichment is required."""
    return batch


def upsert_all(
    ns,
    documents: Iterable[dict[str, Any]],
    batch_size: int,
    *,
    predicate: Callable[[list[dict[str, Any]]], bool] | None = None,
    enrich_fn: Callable[
        [list[dict[str, Any]]], list[dict[str, Any]]
    ] = no_op_enrich,
    force: bool = False,
    progress_bar_total: int | None = None,
    limit: int | None = None,
    schema: Mapping[str, Any],
    distance_metric: DistanceMetric = "cosine_distance",
) -> None:
    """Batch and upsert documents that pass the predicate into a namespace.

    By default, a batch is upserted only when its first document ID does not
    already exist in the namespace.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")

    if force:
        drop(ns)

    progress: Any | None = None
    if progress_bar_total is not None:
        try:
            tqdm = getattr(import_module("tqdm"), "tqdm")
        except ImportError:
            pass
        else:
            progress = tqdm(total=progress_bar_total)

    document_iter = iter(documents)
    documents_processed = 0
    try:
        while limit is None or documents_processed < limit:
            batch = list(islice(document_iter, batch_size))
            if not batch:
                break
            batch_count = len(batch)
            should_upsert = (
                predicate(batch)
                if predicate is not None
                else not exists(ns, batch[0]["id"])
            )
            if should_upsert:
                batch = enrich_fn(batch)
                ns.write(
                    upsert_rows=batch,
                    distance_metric=distance_metric,
                    schema=dict(schema),
                )
            documents_processed += batch_count
            if progress is not None:
                progress.update(batch_size)
    finally:
        if progress is not None:
            progress.close()
