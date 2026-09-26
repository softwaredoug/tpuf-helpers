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


def test_upsert_all(test_namespace, test_docs):
    schema = {"text": {"type": "string"}}
    batch_docs = [
        {**test_docs[0], "vector": [0.1, 0.2]},
        {**test_docs[1], "vector": [0.2, 0.3]},
    ]
    batches = iter([[batch_docs[0]], [batch_docs[1]]])

    upsert_all(test_namespace, batches, schema=schema)

    assert count(test_namespace) == len(test_docs)

    changed_doc = [
        {"id": "doc-1", "text": "should be skipped", "vector": [0.3, 0.4]}
    ]
    upsert_all(test_namespace, iter([changed_doc]), schema=schema)
    document = fetch(test_namespace, "doc-1")
    assert document is not None
    assert document["text"] == "first test document"

    custom_batches = [
        [
            {
                "id": "doc-3",
                "text": "selected by predicate",
                "vector": [0.4, 0.5],
            }
        ],
        [
            {
                "id": "doc-4",
                "text": "skipped by predicate",
                "vector": [0.5, 0.6],
            }
        ],
    ]
    upsert_all(
        test_namespace,
        iter(custom_batches),
        predicate=lambda batch: batch[0]["id"] == "doc-3",
        schema=schema,
    )
    assert exists(test_namespace, "doc-3")
    assert not exists(test_namespace, "doc-4")

    forced_doc = [
        {"id": "doc-5", "text": "after force drop", "vector": [0.6, 0.7]}
    ]
    upsert_all(test_namespace, iter([forced_doc]), force=True, schema=schema)
    assert count(test_namespace) == 1
    document = fetch(test_namespace, "doc-5")
    assert document is not None
    assert document["text"] == "after force drop"
