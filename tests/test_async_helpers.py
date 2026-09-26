import pytest

from tpuf_helpers.async_helpers import count, drop, exists, fetch


@pytest.mark.asyncio
async def test_async_helpers(async_namespace, test_docs):
    await async_namespace.write(upsert_rows=test_docs)

    assert await count(async_namespace) == len(test_docs)
    assert await exists(async_namespace, "doc-1")
    assert not await exists(async_namespace, "missing")
    document = await fetch(async_namespace, "doc-1")
    assert document is not None
    assert document["text"] == "first test document"

    await drop(async_namespace)
    assert await count(async_namespace) == 0


@pytest.mark.asyncio
async def test_async_fetch_and_exists_for_missing_namespace(async_namespace):
    assert await fetch(async_namespace, "missing") is None
    assert not await exists(async_namespace, "missing")


@pytest.mark.asyncio
async def test_async_fetch_and_exists_for_missing_document(
    async_namespace, test_docs
):
    await async_namespace.write(upsert_rows=test_docs)

    assert await fetch(async_namespace, "missing") is None
    assert not await exists(async_namespace, "missing")
