# lexe
[![nox](https://github.com/level12/lexe/actions/workflows/nox.yaml/badge.svg)](https://github.com/level12/lexe/actions/workflows/nox.yaml)

## Deploy modes

Services support three deploy modes via `services.<name>.deploy`:

- `always`: normal app services. They are part of the main deploy group and are recreated on each
  deploy.
- `contingent`: dependency services that should be available for deploy hooks and app startup, but
  are not normally recreated unless `--restart-all` is used.
- `exclusive`: app services that are part of the main deploy group, but should be stopped before
  `start-pre` hooks run.

Use `exclusive` when `start-pre` needs a short maintenance window, especially for destructive or
connection-sensitive database tasks such as dropping and recreating a database before reseeding it.
That lets `lexe` stop the existing service first, run the pre-start hooks without live app
connections, and then start the service again.

## Dev


### Copier Template

Project structure and tooling mostly derives from the [Coppy](https://github.com/level12/coppy),
see its documentation for context and additional instructions.

This project can be updated from the upstream repo, see
[Updating a Project](https://github.com/level12/coppy?tab=readme-ov-file#template-updates).


### Project Setup

From zero to hero (passing tests that is):

1. Ensure [host dependencies](https://github.com/level12/coppy/wiki/Mise) are installed

2. Start docker service dependencies (if applicable):

   `docker compose up -d`

3. Sync [project](https://docs.astral.sh/uv/concepts/projects/) virtualenv w/ lock file:

   `uv sync`

4. Configure pre-commit:

   `pre-commit install`

5. Run tests:

   `nox`


### Versions

Versions are date based.  A `bump` action exists to help manage versions:

```shell

  # Show current version
  mise bump --show

  # Bump version based on date, tag, and push:
  mise bump

  # See other options
  mise bump -- --help
```
