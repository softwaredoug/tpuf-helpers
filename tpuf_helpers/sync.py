from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from itertools import islice
from typing import Any

from turbopuffer import NotFoundError
from turbopuffer.types import DistanceMetric, Row


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
    show_progress: bool = False,
    progress_total: int | None = None,
    schema: Mapping[str, Any],
    distance_metric: DistanceMetric = "cosine_distance",
) -> None:
    """Batch and upsert documents that pass the predicate into a namespace.

    By default, a batch is upserted only when its first document ID does not
    already exist in the namespace.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    if force:
        drop(ns)

    progress: Any | None = None
    if show_progress:
        try:
            tqdm = getattr(import_module("tqdm"), "tqdm")
        except ImportError:
            pass
        else:
            progress = tqdm(total=progress_total)

    document_iter = iter(documents)
    try:
        while batch := list(islice(document_iter, batch_size)):
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
            if progress is not None:
                progress.update(batch_size)
    finally:
        if progress is not None:
            progress.close()
