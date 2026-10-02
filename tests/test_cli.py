import io
import json
from types import SimpleNamespace

import pytest

import tpuf_helpers.cli as cli


class FakeClient:
    def __init__(self, region):
        self.region = region
        self.requested_namespace = None
        self.closed = False

    def namespace(self, name):
        self.requested_namespace = name
        return SimpleNamespace(name=name)

    def close(self):
        self.closed = True


def install_fake_client(monkeypatch, *, region="gcp-us-central1"):
    client = FakeClient(region)
    regions = []

    def create_client(*, region):
        regions.append(region)
        client.region = region
        return client

    monkeypatch.setenv("TURBOPUFFER_API_KEY", "test-key")
    monkeypatch.delenv("TURBOPUFFER_REGION", raising=False)
    monkeypatch.setattr(cli, "Turbopuffer", create_client)
    return client, regions


def test_ls_prints_ids_and_forwards_prefix(monkeypatch, capsys):
    client, regions = install_fake_client(monkeypatch)
    calls = []
    monkeypatch.setattr(
        cli,
        "ls",
        lambda target, *, prefix: calls.append((target, prefix))
        or [SimpleNamespace(id="prod-a"), SimpleNamespace(id="prod-b")],
    )

    assert cli.main(["ls", "--prefix", "prod-"]) == 0

    assert capsys.readouterr().out.splitlines() == ["prod-a", "prod-b"]
    assert calls == [(client, "prod-")]
    assert regions == ["gcp-us-central1"]
    assert client.closed


def test_region_option_overrides_environment(monkeypatch, capsys):
    client, regions = install_fake_client(monkeypatch)
    monkeypatch.setenv("TURBOPUFFER_REGION", "gcp-europe-west1")
    monkeypatch.setattr(cli, "ls", lambda *_args, **_kwargs: [])

    assert cli.main(["--region", "aws-us-east-1", "ls"]) == 0

    assert regions == ["aws-us-east-1"]
    assert client.region == "aws-us-east-1"
    assert capsys.readouterr().out == ""


def test_ls_uses_region_from_environment(monkeypatch, capsys):
    _, regions = install_fake_client(monkeypatch)
    monkeypatch.setenv("TURBOPUFFER_REGION", "gcp-europe-west1")
    monkeypatch.setattr(cli, "ls", lambda *_args, **_kwargs: [])

    assert cli.main(["ls"]) == 0

    assert regions == ["gcp-europe-west1"]
    assert capsys.readouterr().out == ""


def test_ls_requires_api_key(monkeypatch, capsys):
    monkeypatch.delenv("TURBOPUFFER_API_KEY", raising=False)
    constructed = []
    monkeypatch.setattr(cli, "Turbopuffer", lambda **kwargs: constructed.append(kwargs))

    assert cli.main(["ls"]) == 1

    assert constructed == []
    assert "TURBOPUFFER_API_KEY" in capsys.readouterr().err


def test_drop_requires_yes_when_input_is_not_interactive(monkeypatch, capsys):
    client, _ = install_fake_client(monkeypatch)
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    dropped = []
    monkeypatch.setattr(cli, "drop", dropped.append)

    assert cli.main(["drop", "old-index"]) == 1

    assert client.requested_namespace == "old-index"
    assert dropped == []
    assert "--yes" in capsys.readouterr().err


def test_drop_prompts_and_cancels(monkeypatch, capsys):
    client, _ = install_fake_client(monkeypatch)

    class TTYInput(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TTYInput("n\n"))
    dropped = []
    monkeypatch.setattr(cli, "drop", dropped.append)

    assert cli.main(["drop", "old-index"]) == 1

    assert client.requested_namespace == "old-index"
    assert dropped == []
    assert "Drop cancelled" in capsys.readouterr().err


def test_drop_proceeds_after_interactive_confirmation(monkeypatch, capsys):
    client, _ = install_fake_client(monkeypatch)

    class TTYInput(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(cli.sys, "stdin", TTYInput("yes\n"))
    dropped = []
    monkeypatch.setattr(cli, "drop", dropped.append)

    assert cli.main(["drop", "old-index"]) == 0

    assert dropped == [SimpleNamespace(name="old-index")]
    assert "Drop completed" in capsys.readouterr().out
    assert client.closed


def test_drop_yes_skips_prompt_and_drops_namespace(monkeypatch, capsys):
    client, _ = install_fake_client(monkeypatch)
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(""))
    dropped = []
    monkeypatch.setattr(cli, "drop", dropped.append)

    assert cli.main(["drop", "old-index", "--yes"]) == 0

    assert dropped == [SimpleNamespace(name="old-index")]
    assert "Drop completed" in capsys.readouterr().out
    assert client.closed


@pytest.mark.parametrize(
    ("args", "limit"),
    [(["sample", "docs"], 2), (["sample", "docs", "--limit", "3"], 3)],
)
def test_sample_prints_at_most_limit_json_rows(monkeypatch, capsys, args, limit):
    client, _ = install_fake_client(monkeypatch)
    calls = []

    class FakeRow:
        def __init__(self, doc_id):
            self.doc_id = doc_id

        def model_dump(self, *, mode):
            assert mode == "json"
            return {"id": self.doc_id}

    rows = [FakeRow(f"doc-{index}") for index in range(5)]

    def fake_fetch_all(namespace, *, page_size, limit):
        calls.append((namespace, page_size, limit))
        return iter(rows)

    monkeypatch.setattr(cli, "fetch_all", fake_fetch_all)

    assert cli.main(args) == 0

    output_rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert output_rows == [{"id": f"doc-{index}"} for index in range(limit)]
    assert calls == [(SimpleNamespace(name="docs"), limit, limit)]
    assert client.closed


def test_sample_zero_limit_prints_nothing(monkeypatch, capsys):
    install_fake_client(monkeypatch)
    calls = []
    monkeypatch.setattr(
        cli,
        "fetch_all",
        lambda *args, **kwargs: calls.append((args, kwargs)) or iter(()),
    )

    assert cli.main(["sample", "docs", "--limit", "0"]) == 0

    assert len(calls) == 1
    assert calls[0][1] == {"page_size": 1, "limit": 0}
    assert capsys.readouterr().out == ""


def test_sample_rejects_negative_limit(monkeypatch):
    install_fake_client(monkeypatch)

    with pytest.raises(SystemExit):
        cli.main(["sample", "docs", "--limit", "-1"])
