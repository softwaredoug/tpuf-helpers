import os
from uuid import uuid4

import pytest
from turbopuffer import Turbopuffer

from tpuf_helpers.sync import drop


@pytest.fixture
def tpuf_client():
    client = Turbopuffer(
        api_key=os.environ["TURBOPUFFER_API_KEY"],
        region=os.environ.get("TURBOPUFFER_REGION", "gcp-us-central1"),
    )
    yield client
    client.close()


@pytest.fixture
def test_docs():
    return [
        {"id": "doc-1", "text": "first test document"},
        {"id": "doc-2", "text": "second test document"},
    ]


@pytest.fixture
def test_namespace(tpuf_client):
    namespace = tpuf_client.namespace(f"test-tpuf-helpers-{uuid4().hex}")
    yield namespace
    drop(namespace)
