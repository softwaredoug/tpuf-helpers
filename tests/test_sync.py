from tpuf_helpers.sync import count, drop, exists, fetch


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
