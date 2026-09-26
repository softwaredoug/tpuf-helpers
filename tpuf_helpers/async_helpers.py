from turbopuffer import NotFoundError
from turbopuffer.types import Row


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
