import sys
from types import ModuleType
from uuid import uuid4

from tpuf_helpers.sync import count, drop, exists, fetch, fetch_all, ls, upsert_all


def test_ls_returns_empty_for_unmatched_prefix(tpuf_client):
    prefix = f"test-tpuf-helpers-ls-no-match-{uuid4().hex}"

    assert list(ls(tpuf_client, prefix=prefix)) == []


def test_ls_lists_all_namespaces_when_prefix_is_omitted():
    expected = [object(), object()]

    class ClientStub:
        def __init__(self):
            self.options = None

        def namespaces(self, **options):
            self.options = options
            return iter(expected)

    client = ClientStub()

    assert list(ls(client)) == expected
    assert client.options == {}


def test_ls_passes_listing_options_to_client():
    class ClientStub:
        def __init__(self):
            self.options = None

        def namespaces(self, **options):
            self.options = options
            return iter(())

    client = ClientStub()

    assert list(ls(client, prefix="test-data", page_size=1)) == []
    assert client.options == {"prefix": "test-data", "page_size": 1}


def test_ls_filters_by_prefix_and_iterates_all_pages(tpuf_client):
    prefix = f"test-tpuf-helpers-ls-{uuid4().hex}"
    names = [prefix, f"{prefix}-child"]
    namespaces = [tpuf_client.namespace(name) for name in names]

    try:
        for namespace in namespaces:
            namespace.write(upsert_rows=[{"id": "doc-1"}])

        # A one-item page forces the client iterator to follow its cursor.
        listed = list(ls(tpuf_client, prefix=prefix, page_size=1))
    finally:
        for namespace in namespaces:
            drop(namespace)

    # Don't assert service ordering: only membership and prefix behavior matter.
    assert {namespace.id for namespace in listed} == set(names)


def test_sync_helpers(test_namespace, test_docs):
    test_namespace.write(upsert_rows=test_docs)

    assert count(test_namespace) == len(test_docs)
    assert exists(test_namespace, "doc-1")
    assert not exists(test_namespace, "missing")
    document = fetch(test_namespace, "doc-1")
    assert document is not None
    assert document["text"] == "first test document"

    drop(test_namespace)
    assert count(test_namespace) == 0


def test_fetch_and_exists_for_missing_namespace(test_namespace):
    assert fetch(test_namespace, "missing") is None
    assert not exists(test_namespace, "missing")


def test_fetch_and_exists_for_missing_document(test_namespace, test_docs):
    test_namespace.write(upsert_rows=test_docs)

    assert fetch(test_namespace, "missing") is None
    assert not exists(test_namespace, "missing")


def test_fetch_all_returns_documents_across_pages(test_namespace):
    documents = [
        {"id": "doc-1", "text": "first", "category": "one"},
        {"id": "doc-2", "text": "second", "category": "two"},
    ]
    test_namespace.write(upsert_rows=documents)

    rows = list(fetch_all(test_namespace, page_size=1))

    assert [row["id"] for row in rows] == ["doc-1", "doc-2"]
    assert [row["category"] for row in rows] == ["one", "two"]


def test_fetch_all_selects_attributes(test_namespace):
    documents = [
        {"id": "doc-1", "text": "first", "category": "one"},
        {"id": "doc-2", "text": "second", "category": "two"},
    ]
    test_namespace.write(upsert_rows=documents)

    rows = list(fetch_all(test_namespace, include_attributes=["text"], page_size=1))

    assert [row["text"] for row in rows] == ["first", "second"]
    assert all(
        row.model_extra is not None and "category" not in row.model_extra
        for row in rows
    )


def test_fetch_all_returns_nothing_for_missing_namespace(test_namespace):
    assert list(fetch_all(test_namespace)) == []


def test_fetch_all_stops_at_page_boundary_for_limit(test_namespace):
    test_namespace.write(
        upsert_rows=[
            {"id": f"doc-{index}", "text": f"document {index}"}
            for index in range(1, 5)
        ]
    )

    rows = list(fetch_all(test_namespace, page_size=2, limit=1))

    assert [row["id"] for row in rows] == ["doc-1", "doc-2"]


def test_upsert_all_batches_documents(test_namespace, test_docs):
    documents = [
        {**test_docs[0], "vector": [0.1, 0.2]},
        {**test_docs[1], "vector": [0.2, 0.3]},
    ]
    upsert_all(
        test_namespace,
        iter(documents),
        batch_size=2,
        schema={"text": {"type": "string"}},
    )

    assert count(test_namespace) == len(test_docs)


def test_upsert_all_stops_at_batch_boundary_for_limit(test_namespace, test_docs):
    documents = [
        {**test_docs[0], "vector": [0.1, 0.2]},
        {**test_docs[1], "vector": [0.2, 0.3]},
        {"id": "doc-3", "text": "third test document", "vector": [0.3, 0.4]},
    ]

    upsert_all(
        test_namespace,
        iter(documents),
        batch_size=2,
        limit=1,
        schema={"text": {"type": "string"}},
    )

    assert count(test_namespace) == 2
    assert exists(test_namespace, "doc-1")
    assert exists(test_namespace, "doc-2")
    assert not exists(test_namespace, "doc-3")


def test_upsert_all_skips_batch_when_first_document_exists(
    test_namespace, test_docs
):
    test_namespace.write(
        upsert_rows=[{**test_docs[0], "vector": [0.1, 0.2]}],
        distance_metric="cosine_distance",
        schema={"text": {"type": "string"}},
    )
    changed_doc = {
        "id": "doc-1", "text": "should be skipped", "vector": [0.3, 0.4]
    }

    upsert_all(
        test_namespace,
        iter([changed_doc]),
        batch_size=1,
        schema={"text": {"type": "string"}},
    )

    document = fetch(test_namespace, "doc-1")
    assert document is not None
    assert document["text"] == "first test document"


def test_upsert_all_applies_predicate(test_namespace):
    documents = [
        {
            "id": "doc-3",
            "text": "selected by predicate",
            "vector": [0.4, 0.5],
        },
        {
            "id": "doc-4",
            "text": "skipped by predicate",
            "vector": [0.5, 0.6],
        },
    ]

    upsert_all(
        test_namespace,
        iter(documents),
        batch_size=1,
        predicate=lambda batch: batch[0]["id"] == "doc-3",
        schema={"text": {"type": "string"}},
    )

    assert exists(test_namespace, "doc-3")
    assert not exists(test_namespace, "doc-4")


def test_upsert_all_enriches_only_selected_batches(test_namespace):
    documents = [
        {
            "id": "doc-3",
            "text": "selected by predicate",
            "vector": [0.4, 0.5],
        },
        {
            "id": "doc-4",
            "text": "skipped by predicate",
            "vector": [0.5, 0.6],
        },
    ]
    enriched_ids = []

    def enrich(batch):
        enriched_ids.extend(doc["id"] for doc in batch)
        return [{**doc, "text": f'{doc["text"]} (enriched)'} for doc in batch]

    upsert_all(
        test_namespace,
        iter(documents),
        batch_size=1,
        predicate=lambda batch: batch[0]["id"] == "doc-3",
        enrich_fn=enrich,
        schema={"text": {"type": "string"}},
    )

    assert enriched_ids == ["doc-3"]
    enriched_doc = fetch(test_namespace, "doc-3")
    assert enriched_doc is not None
    assert enriched_doc["text"] == "selected by predicate (enriched)"
    assert not exists(test_namespace, "doc-4")


def test_upsert_all_force_drops_existing_documents(test_namespace, test_docs):
    test_namespace.write(
        upsert_rows=[{**test_docs[0], "vector": [0.1, 0.2]}],
        distance_metric="cosine_distance",
        schema={"text": {"type": "string"}},
    )
    forced_doc = {
        "id": "doc-5", "text": "after force drop", "vector": [0.6, 0.7]
    }

    upsert_all(
        test_namespace,
        iter([forced_doc]),
        batch_size=1,
        force=True,
        schema={"text": {"type": "string"}},
    )

    assert count(test_namespace) == 1
    assert not exists(test_namespace, "doc-1")
    document = fetch(test_namespace, "doc-5")
    assert document is not None
    assert document["text"] == "after force drop"


def test_upsert_all_progress_advances_for_skipped_batches(monkeypatch):
    class FakeProgress:
        def __init__(self, total):
            self.total = total
            self.updates = []
            self.closed = False

        def update(self, amount):
            self.updates.append(amount)

        def close(self):
            self.closed = True

    progress_bars = []

    def create_progress(total=None):
        progress = FakeProgress(total)
        progress_bars.append(progress)
        return progress

    tqdm_module = ModuleType("tqdm")
    setattr(tqdm_module, "tqdm", create_progress)
    monkeypatch.setitem(sys.modules, "tqdm", tqdm_module)

    upsert_all(
        object(),
        iter([
            {"id": "doc-1"},
            {"id": "doc-2"},
            {"id": "doc-3"},
            {"id": "doc-4"},
        ]),
        batch_size=2,
        predicate=lambda batch: False,
        progress_bar_total=4,
        schema={},
    )

    progress = progress_bars[0]
    assert progress.total == 4
    assert progress.updates == [2, 2]
    assert progress.closed


def test_upsert_all_progress_works_without_tqdm(monkeypatch):
    def missing_tqdm(_module_name):
        raise ImportError("tqdm is not installed")

    monkeypatch.setattr("tpuf_helpers.sync.import_module", missing_tqdm)

    upsert_all(
        object(),
        iter([{"id": "doc-1"}]),
        batch_size=1,
        predicate=lambda batch: False,
        progress_bar_total=1,
        schema={},
    )
