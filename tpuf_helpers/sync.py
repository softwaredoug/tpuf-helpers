from turbopuffer.types import NamespaceQueryResponse, Row
from turbopuffer import NotFoundError

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
