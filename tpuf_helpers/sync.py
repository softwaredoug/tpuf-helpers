from collections.abc import Callable, Iterable, Mapping
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


def upsert_all(
    ns,
    batches: Iterable[list[dict[str, Any]]],
    *,
    predicate: Callable[[list[dict[str, Any]]], bool] | None = None,
    force: bool = False,
    schema: Mapping[str, Any],
    distance_metric: DistanceMetric = "cosine_distance",
) -> None:
    """Upsert batches that pass the predicate into a namespace.

    By default, a batch is upserted only when its first document ID does not
    already exist in the namespace.
    """
    if force:
        drop(ns)

    for batch in batches:
        if not batch:
            continue

        should_upsert = (
            predicate(batch)
            if predicate is not None
            else not exists(ns, batch[0]["id"])
        )
        if should_upsert:
            ns.write(
                upsert_rows=batch,
                distance_metric=distance_metric,
                schema=dict(schema),
            )
