from tpuf_helpers.sync import count, drop, exists, fetch, upsert_all


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
