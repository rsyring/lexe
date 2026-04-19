# Code Review: `lexe` Implementation vs. Spec + Agent Instructions

Scope: `src/lexe/*`, `tests/lexe_tests/*`, `examples/{hello,flask}`.

Loaded conditional instructions: `agent-specs`, `mise-uv`, `python-cli`,
`python-general`, `python-cli-click-logging-integration`.

## Summary

The implementation covers the "initial deploy phase" described in
`spec/2026-04-19-deploy.md` and the provision/destroy lifecycle in
`spec/2026-04-19-provision.md`. Deferred items (lock, secrets, hooks,
healthcheck polling, `lexe-logs.md`, image prune, no-op/`--force`, `status`)
are all acknowledged in those specs and are not flagged below.

The main issues are: missing logging integration that the parent spec
explicitly pulls in, test style violations against `python-general`, an
overly-broad exception wrap in `procs.sub_run`, and a handful of small
CLI/config inconsistencies.

## Agent Instruction Violations

### Tests use `monkeypatch` instead of `unittest.mock`

`python-general` says: "Use `unittest.mock` instead of pytest's `monkeypatch`
fixture". `monkeypatch` is used throughout `test_cli.py`, `test_deploy.py`,
`test_provision.py` (with `monkeypatch.setattr` on `lexe.deploy.sub_run`,
`lexe.provision.ssh`, etc.). These should be converted to
`unittest.mock.patch` / `patch.object`.

### CLI logging not wired per `python-cli-click-logging-integration`

Parent spec (`Observability / UX`) explicitly says: "Reference the
python-cli-click-logging-integration instructions." That recipe provides
`--quiet|--info|--debug` flags and a `colorlog` handler. Current
implementation uses only `click.echo` for user output and has no log-level
CLI options. `procs.py` does `log.debug(...)` but nothing configures the
root logger, so those messages are silently dropped. `colorlog` is also not
a declared dependency.

This is the single largest gap from the parent spec's stated
observability decision.

### `procs.sub_run` broad `except Exception`

`python-general`: "Only catch exceptions when you have something meaningful
to do with them. DO NOT catch them just to minimally wrap them or add a
trivial message and re-throw."

`src/lexe/procs.py`:

```python
except Exception as e:
    raise CalledProcessError('n/a', args, '', '') from e
```

Two problems:
1. It swallows unrelated exceptions (e.g. `FileNotFoundError` when the
   executable is missing) and re-raises a misleading `CalledProcessError`,
   losing the original type for callers.
2. `subprocess.CalledProcessError(returncode, cmd, ...)` expects
   `returncode: int`. Passing the string `'n/a'` will break any downstream
   code that treats `.returncode` as int (including `__str__` formatting
   done by `CalledProcessError`).

Recommend removing the catch entirely and letting the original exception
surface.

## Code Issues

### `cli.destroy` inconsistent with `provision` / `deploy`

`cli.provision` / `cli.deploy` do `find_lexe_fpath(config_fpath)` and then
derive `app_dpath = config_fpath.parent`. `cli.destroy` instead calls
`LexeConfig.find_lexe(config_fpath)` directly. The code paths should be
identical for config discovery, or share a helper. As written, `destroy`
with the default `lexe.yaml` won't walk upward from a nested working
directory, but `provision`/`deploy` will, because
`find_lexe_fpath('lexe.yaml')` short-circuits on the `.yaml` suffix and
returns the path unresolved.

### `find_lexe_fpath` accepts non-existent yaml paths

When `start_at.suffix == '.yaml'`, the function returns the path without
checking `.exists()`. The "missing config" error then surfaces deep inside
`yaml.safe_load`. Minor, but inconsistent with the explicit error raised
for the directory-search branch.

### `find_upwards` never checks filesystem root

`while d != root` skips the root itself. If `lexe.yaml` existed at `/`
(unlikely but valid), it would be missed. Trivial edge case; flagging for
completeness.

### `--config-fpath` vs. app-root argument

Parent spec has a TODO: take the app root, not the config file. Worth
aligning with that TODO before more commands land, since `app_dpath` is
already the operative value inside each command.

### User-facing error path for subprocess failures

`procs.CalledProcessError` is not a `click.ClickException`, so a failed
`docker build` etc. will surface as a traceback to the end user rather
than a clean "Error: ..." line. Provision/deploy do wrap some conditions
in `ClickException`, but not subprocess failures.

## Spec vs. Code Source-of-Truth Drift

`agent-specs.md`: "Do not duplicate implementation details or exact
commands into spec documents when the code is the source of truth."

Both the parent spec and deploy spec contain command-level detail (e.g.
`flock lexe-deploy.lock`, `-f compose.yaml -f compose.server.yaml`,
`sudo systemctl restart docker`, `docker pussh <vm-host>`,
`docker image prune --force`). The user flagged this is acceptable deviation
for now; noting it so future spec edits can trim implementation text once
the code covers those paths.

## Observations (not issues)

- Dataclasses, pathlib usage, class-based tests, `ensure_*` idempotency
  patterns, and small module boundaries match `python-general` guidance.
- `LexeConfig` uses `yaml.safe_load` + pyserde `rename` correctly.
- Integration tests (`test_examples.py`) correctly gate on
  `@pytest.mark.integration` and clean up via `Destroy` in `finally`.
- `examples/hello/compose.server.yaml` intentionally uses a non-privileged
  port (`5678:5678`) and `examples/flask` uses `8000:8000` with
  `public-service: web`; both match the "exe.dev HTTP proxy maps the
  service port" direction noted as an open item in the parent spec.

## Recommended Next Actions (in priority order)

1. Convert tests from `monkeypatch` to `unittest.mock`.
2. Wire `--quiet|--info|--debug` + `colorlog` per the referenced
   `mu-logs.py` recipe; replace at least subprocess tracing with
   `log.debug` output that is visible under `--debug`.
3. Remove the blanket `except Exception` wrap in `procs.sub_run`.
4. Unify config discovery between `provision`, `deploy`, and `destroy`
   (single helper, `.exists()` check, consistent `app_dpath` derivation),
   and decide whether to pivot to an app-root positional argument per the
   parent spec TODO.
5. Wrap subprocess failures in `click.ClickException` at the command
   boundary so CLI users see clean error output.
