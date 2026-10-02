"""Command-line interface for basic Turbopuffer namespace operations."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from itertools import islice
from typing import Any

from turbopuffer import APIError, Turbopuffer

from tpuf_helpers.sync import drop, fetch_all, ls


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tpuf",
        description="Basic Turbopuffer namespace operations.",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("TURBOPUFFER_REGION", "gcp-us-central1"),
        help="Turbopuffer region (default: TURBOPUFFER_REGION or gcp-us-central1)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    ls_parser = commands.add_parser("ls", help="list namespaces")
    ls_parser.add_argument(
        "--prefix", help="only list namespace IDs that start with this prefix"
    )

    drop_parser = commands.add_parser("drop", help="delete a namespace")
    drop_parser.add_argument("namespace", help="namespace to delete")
    drop_parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the interactive confirmation",
    )

    sample_parser = commands.add_parser(
        "sample", help="print a sample of documents from a namespace"
    )
    sample_parser.add_argument("namespace", help="namespace to sample")
    sample_parser.add_argument(
        "--limit",
        type=_non_negative_int,
        default=2,
        help="maximum number of documents to print (default: 2)",
    )

    return parser


def _confirm_drop(namespace: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True

    if not sys.stdin.isatty():
        print(
            f"tpuf: refusing to drop {namespace!r} without an interactive "
            "confirmation; pass --yes to proceed",
            file=sys.stderr,
        )
        return False

    try:
        answer = input(
            f"Delete namespace {namespace!r} and all its documents? [y/N] "
        )
    except EOFError:
        answer = ""

    if answer.strip().lower() in {"y", "yes"}:
        return True

    print("Drop cancelled.", file=sys.stderr)
    return False


def _run_command(args: argparse.Namespace, client: Any) -> int:
    if args.command == "ls":
        for namespace in ls(client, prefix=args.prefix):
            print(namespace.id)
        return 0

    namespace = client.namespace(args.namespace)
    if args.command == "drop":
        if not _confirm_drop(args.namespace, assume_yes=args.yes):
            return 1
        drop(namespace)
        print(f"Drop completed for namespace {args.namespace!r}.")
        return 0

    if args.command == "sample":
        # fetch_all may yield the rest of its last page past its limit. Keep
        # the request page small and cap output exactly at the requested count.
        page_size = max(1, min(args.limit, 10_000))
        rows = fetch_all(namespace, page_size=page_size, limit=args.limit)
        for row in islice(rows, args.limit):
            print(json.dumps(row.model_dump(mode="json")))
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not os.environ.get("TURBOPUFFER_API_KEY"):
        print(
            "tpuf: set TURBOPUFFER_API_KEY to authenticate with Turbopuffer",
            file=sys.stderr,
        )
        return 1

    client = None
    try:
        client = Turbopuffer(region=args.region)
        return _run_command(args, client)
    except APIError as exc:
        print(f"tpuf: {exc}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()
