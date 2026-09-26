from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from itertools import islice
from typing import Any

from turbopuffer import NotFoundError
from turbopuffer.types import DistanceMetric, Row

from tpuf_helpers.sync import no_op_enrich


async def fetch(ns, doc_id: str) -> Row | None:
    """Fetch a document by id asynchronously."""
    try:
        result = await ns.query(
            filters=("id", "Eq", doc_id),
            rank_by=("id", "asc"),
            limit=1,
            include_attributes=True,
        )

        return result.rows[0] if result.rows else None
    except NotFoundError:
        return None


async def exists(ns, doc_id: str) -> bool:
    """Check asynchronously if a document exists."""
    return await fetch(ns, doc_id) is not None


async def count(ns):
    """Count documents in a namespace asynchronously."""
    try:
        result = await ns.query(aggregate_by={"count": ("Count",)})
        return result.aggregations["count"]
    except NotFoundError:
        return 0


async def drop(ns):
    """Drop all documents from a namespace asynchronously."""
    try:
        await ns.delete_all()
    except NotFoundError:
        pass


async def upsert_all(
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
    schema: Mapping[str, Any],
    distance_metric: DistanceMetric = "cosine_distance",
) -> None:
    """Batch and asynchronously upsert documents that pass the predicate.

    By default, a batch is upserted only when its first document ID does not
    already exist in the namespace.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    if force:
        await drop(ns)

    progress: Any | None = None
    if progress_bar_total is not None:
        try:
            tqdm = getattr(import_module("tqdm"), "tqdm")
        except ImportError:
            pass
        else:
            progress = tqdm(total=progress_bar_total)

    document_iter = iter(documents)
    try:
        while batch := list(islice(document_iter, batch_size)):
            should_upsert = (
                predicate(batch)
                if predicate is not None
                else not await exists(ns, batch[0]["id"])
            )
            if should_upsert:
                batch = enrich_fn(batch)
                await ns.write(
                    upsert_rows=batch,
                    distance_metric=distance_metric,
                    schema=dict(schema),
                )
            if progress is not None:
                progress.update(batch_size)
    finally:
        if progress is not None:
            progress.close()
