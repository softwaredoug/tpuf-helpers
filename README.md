# Turbopuffer helpers

Convenience helpers and a small command-line interface for common Turbopuffer
namespace operations.

## CLI

From a checkout of this repository, install the `tpuf` command with uv:

```sh
uv tool install .
```

For a development install that uses the working tree directly, run
`uv tool install --editable .`. If uv reports that its tool binary directory is
not on `PATH`, run `uv tool update-shell` and restart the shell.

Set `TURBOPUFFER_API_KEY` before running commands. The region defaults to
`TURBOPUFFER_REGION`, or `gcp-us-central1` if that variable is unset. Override
it with the global `--region` option (before the command).

```sh
tpuf ls
tpuf ls --prefix test-
tpuf sample my-namespace
tpuf sample my-namespace --limit 5
tpuf drop old-namespace
tpuf drop old-namespace --yes
```

`ls` prints one namespace ID per line. `sample` prints up to two documents by
default as JSON Lines. `drop` asks for confirmation when run interactively;
pass `--yes` to skip the prompt, such as in scripts. A non-interactive drop
without `--yes` is refused.

The CLI is also available as a Python module:

```sh
python -m tpuf_helpers --help
```
