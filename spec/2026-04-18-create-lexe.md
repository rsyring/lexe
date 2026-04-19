# Spec for lexe

`lexe` is a cli tool used to manage exe.dev VMs and deploy apps to those vms.


## References

- [exe.dev docs](https://exe.dev/llms.txt)
- [unregistry repo](https://github.com/psviderski/unregistry)
- `~/projects/doist-pkg/tasks/doist-server`: existing deployment script that can be reviewed for
  patterns/ideas
- `~/projects/code-examples/configs/juke-config.py`: for app config file processing example


## Design Positioning

- Closest analog: Kamal v2, but smaller and more opinionated for single-deployer / personal use.
- v1 intentionally skips proxy-based cutover and accepts stop-then-start deploys.
- A future reduced-downtime path could use a suffixed compose project plus proxy cutover.


## App / VM Setup

- Each app gets it's own VM
- If VM doesn't exist, create it
- Do some basic VM prep like turning on automatic updates and applying existing host hardening
  scripts for Ubuntu 24.04 (details TBD)
- If public, use exe.dev ssh commands to make VM's web app publically accessible
- Make the app's HTTP(S) port(s) the default ones for the VM


## App Deployments

- Dockerfile for the deployable container
- Docker Compose
    - compose.yaml: base file shared by local and remote
    - compose.server.yaml: used explicitly with deploy logic
    - compose.override.yaml: for local dev, automatically used by docker compose
- `lexe deploy` must always pass `-f compose.yaml -f compose.server.yaml` explicitly so
  `compose.override.yaml` never leaks into deploys
- Build docker image in local Docker image store
    - Tag each unique build so we can target it as part of the deploy
- Use `docker pussh` to transfer image to remote
- Stop existing service(s) if running
- Run pre-start hook: used for things like database migrations
- Start services
- Run post-start hook


## Open Questions

### Product / Scope

- Is `lexe` intended only for single-app, single-VM deployments, or should v1 support multi-service apps
  like web + worker?

We need to support multi-service apps like web + worker.  We also need to be able to configure supporting services for the app, like a database server.

- Is the initial target just your own projects, or should the design aim for broader reuse?

Just my own projects for now

- Are there explicit non-goals for v1 that should be called out now?

Probably but we'll define those as we go.

### CLI Shape

- What commands do you want in the first usable version?

    - deploy: deploy the app
    - provision: create/init/prep the VM.  Idempotent so it can be used to change configuration if/when needed.
    - status: details TBD

- Should `deploy` automatically ensure the VM exists and is prepared, or should provisioning be a
  separate command?

See above

- Do you want `lexe` to also provide convenience commands like `ssh`, `logs`, `status`, or should
  that wait until later?

wait until later

### App Config

- Where should app configuration live: in each app repo, in a central inventory, or both?

each app repo

- What config format do you want to use?

yaml

- What fields are required for an app definition?

We'll figure that out as we go along

- How should secrets and environment variables be represented in config vs injected at deploy time?

Every app will get a 1password service account. We will use the `op` CLI to hydrate a committed
env template file at deploy time.

Default path: `deploy/default.env`

That file contains `op://` references, is safe to commit, and is configurable in `lexe.yaml` so we
can support variants like `deploy/staging.env` and `deploy/prod.env` later.

See `./spec/deploy-secrets-example.sh` as a reference.

### VM Lifecycle

- How should a VM be identified for an app: deterministic name, stored ID, or both?

Make that part of the config: `vm-host-name`

If we get an error when using that name, we'll surfice it to the user and let them take action.

- If a VM already exists but is missing expected setup, should `lexe` repair it automatically,
  warn, or fail?

that would be the provision step and it should try to bring the vm into conformance, hence provision being an idempotent command.

- What exact VM prep tasks are required for MVP?

They are going to be Ubuntu 24.04 servers so the only thing I can think of is that we want to turn
on automatic updates and set a restart window if needed.  Don't work on that now, I have scripts
that we can use for that.


### Public Networking

- What does “make the app's HTTP(S) port(s) the default ones for the VM” mean in concrete terms?

See the exe.dev documentation.  They explain that exe.dev provides an http proxy and we can set it
to map the app's port, like 8000, to port 80.  Then again, we might just be able to use port 80/443
in the docker compose for the service.  We'll need to iterate through that to see what the right
config is.

- Should v1 support custom domains and TLS, or only basic public exposure?

exe.dev handles TLS.  We won't do custom domains right away.

- Should non-HTTP services be supported in v1?

Not publically, no.


### Build / Image Transfer

- What exactly is meant by “local registry” here: local Docker images, a registry container, or
  something else?

The local docker daemon images.  Read the unregistry repo to see how it works to get context.

- How should unique build tags be generated?

Use `vYYYY-MM-DD-<sha7>` based on the current git commit SHA.

`lexe deploy` should fail fast if the working tree is dirty.

- Should `lexe deploy` always build locally, or should it also support deploying an already-built
  image tag?

    - Build locally, which should be really fast if already built and no changes
    - use `docker pussh` to sync the image to the remote server


### Deploy Behavior

- Is the deploy strategy intentionally stop-then-start, or do you want a path toward reduced
  downtime?

If you can think of a simple way to get green/blue deployments in this context we can discuss it.

I thought that complexity would be too much for the MVP.

- What should count as a successful deploy: containers started, healthcheck passed, HTTP response,
  or something else?

We should define a healthcheck URL in the config that we can run locally.  Not successful until that URL returns a 200 range error code (not just 200, 204 would be ok, etc.).

- If deployment fails after stopping the old service, what is the expected recovery behavior?

Nothing.  Let the dev figure it out.

### Hooks

- Where are pre-start and post-start hooks defined?

In the app's lexe.yaml

- Where do hooks run: local host, remote VM shell, or inside a container?

for now, all hooks are remote and should be ran with the app's deployed image in a container that is automatically removed by docker after it finishes.

- Should a failed pre-start hook abort the deploy?

yes

- Should post-start hooks affect deploy success or just be reported?

just report


### Observability / UX

- What output should `lexe` prioritize: human-readable logs, machine-readable output, or both?

human readable.

Reference the python-cli-click-logging-integration instructions.

- Do you want deploy history or release metadata recorded anywhere?

Let's have a lexe-logs.md file that records the datetime, image tag and hash, etc.

- Should `lexe` offer a dry-run mode in v1?

no



## Concerns

- “One VM per app” is simple, but may be more expensive and operationally heavier than needed.

Acceptable for our use case

- “Stop existing service(s) if running” implies downtime unless health checks and cutover behavior
  are defined.

Acceptable for our use case

- Hooks can become an escape hatch unless their scope and execution model are constrained.

Acceptable for our use case

- Secrets handling is not yet defined and is likely to become a sharp edge if not specified early.

Defined above.


## Decisions Captured

- `lexe` is for personal projects first, not general external reuse.
- Each app gets its own exe.dev VM.
- Apps may have multiple services, including supporting services like databases and workers.
- Initial commands are `provision`, `deploy`, and `status`.
- App config lives in each app repo in `lexe.yaml`.
- Config format is YAML.
- Closest analog is Kamal v2, but `lexe` intentionally skips proxy-based cutover in v1.
- Secrets are hydrated locally using a 1Password service account and `op run --env-file` from a committed template file (default `deploy/default.env`), then passed to remote containers via the Docker API at container create/run time.
- VM identity is provided explicitly by config via `vm-host-name`.
- `provision` is idempotent and is responsible for bringing the VM into conformance.
- Deploys acquire a local `flock` lock on `lexe-deploy.lock` before doing work.
- Release tags use `vYYYY-MM-DD-<sha7>` from the current git commit SHA.
- `deploy` fails fast if the git working tree is dirty.
- If the computed release tag already exists on the remote daemon, `deploy` is a no-op by default.
- `deploy --force` re-runs stop/start, hooks, and healthcheck when the image is already on the VM.
- Deploys build locally, sync the built image to the VM via `docker pussh`, and then manage remote containers from the local machine by targeting the remote Docker daemon over `DOCKER_HOST=ssh://...`.
- `docker compose` must always explicitly select `compose.yaml` and `compose.server.yaml` for deploys.
- Host bind mounts in `compose.server.yaml` refer to paths on the VM; named volumes are preferred.
- Successful deploy means a configured healthcheck URL returns a 2xx status code.
- Pre-start hooks abort deploy on failure. Post-start hooks are report-only.
- Output should be human-readable.
- Deploy history should be recorded in committed `lexe-logs.md` at repo root.
- Successful deploys run `docker image prune --force` on the VM to clear dangling layers.
- No remote deploy directory is required in v1.


## Proposed v1 Non-Goals

- No custom domains in v1.
- No blue/green or canary deployments in v1.
- No automatic rollback in v1.
- No dry-run mode in v1.
- No public exposure for non-HTTP services in v1.
- No central inventory of apps in v1.


## Proposed v1 Repository Contract

Expected repository files:

- `lexe.yaml`: app deployment configuration
- `Dockerfile`: deployable image build definition
- `compose.yaml`: base compose definition shared across environments
- `compose.server.yaml`: deploy-specific compose overrides used by `lexe deploy`
- `compose.override.yaml`: local dev only; not used by `lexe deploy`
- `deploy/default.env`: committed env template with 1Password references consumable by local `op run --env-file`
- `lexe-logs.md`: append-only deploy log written by `lexe` and committed to the repo


## Proposed `lexe.yaml` Schema

Initial fields already implied by the rest of this spec:

- `app-name`
- `vm-host-name`
- `public-service`
- `healthcheck-url`
- `deploy.env-file` (default `deploy/default.env`)
- `hooks.pre-start`
- `hooks.post-start`

## Proposed v1 Command Contract

### `lexe provision`

Responsibilities:

- Validate `lexe.yaml`
- Ensure the target VM exists; create it if not
- Wait for the VM to become reachable over SSH after create / update
- Ensure the Docker Engine is installed and usable on the VM
- Validate local prerequisites needed to target the remote Docker daemon:
    - Docker CLI
    - Docker Compose plugin
    - `docker pussh`
    - `op` CLI
    - `flock`
    - SSH access to the VM
- Ensure VM-level configuration required by the app is present, including invoking existing host
  hardening/setup scripts for Ubuntu 24.04 as needed
- If it's a public service, configure public HTTP exposure for the selected app service

Behavior:

- Idempotent: safe to re-run
- If the VM exists but is partially configured, attempt to repair it
- If a configured VM name is invalid or conflicts, surface the error to the user and stop


### `lexe deploy`

Responsibilities:

- Validate `lexe.yaml`
- Acquire a local lock with `flock lexe-deploy.lock`
- Require a clean git working tree
- Generate a release tag in the form `vYYYY-MM-DD-<sha7>`
- Check whether that release tag already exists on the remote daemon
- Build the app image locally when needed
- Tag the built image with the computed release tag
- Push the image directly to the remote VM with `docker pussh`
- Run local `docker compose -f compose.yaml -f compose.server.yaml` against the remote Docker daemon using local compose files
- Hydrate secrets locally with `op run --env-file` before creating or replacing remote containers
- Stop and replace running services on the remote VM via the remote Docker daemon
- Run configured pre-start hooks as one-off containers on the remote VM via the remote Docker daemon
- Run configured post-start hooks the same way after startup
- Check `healthcheck-url` from the local machine until success or timeout
- Append a deploy record to `lexe-logs.md`
- Run `docker image prune --force` on the VM after a successful deploy

Behavior:

- `deploy` does not implicitly create the VM. User runs `provision` first.
- If local or remote prerequisites are missing, fail with a clear error.
- If the computed release tag already exists on the remote daemon, report that the commit is already deployed and exit successfully.
- `deploy --force` overrides the no-op path when the image is already present: it still skips build + `docker pussh`, but re-runs stop/start, hooks, and healthcheck.
- Failed pre-start hooks abort deploy.
- Failed post-start hooks are reported but do not fail the deploy.
- If healthcheck never succeeds, mark deploy failed and surface the failure. No rollback is attempted.


### `lexe status`

Minimal v1 behavior:

- Show configured app name and VM host name
- Show whether the VM is reachable
- Show whether the compose project appears to be running on the VM
- Show the most recent entry from `lexe-logs.md` if present
- Optionally run the configured healthcheck URL and report the result

Note: `status` should be kept minimal until `provision` and `deploy` are implemented.


## Proposed v1 Execution Model

- `lexe` runs `docker`, `docker compose`, and `op` locally.
- `lexe` targets the remote VM's Docker daemon from the local machine via `DOCKER_HOST=ssh://...`.
- Compose files remain local and are evaluated locally by Docker Compose.
- Deploys must always pass `-f compose.yaml -f compose.server.yaml` explicitly.
- `deploy/default.env` remains local and is hydrated locally by `op run --env-file`.
- Hydrated secret values are sent to the remote Docker daemon as part of container configuration.
- Secret values are not baked into the image; they are attached to running containers at deploy time.
- Host bind mounts in `compose.server.yaml` refer to remote VM paths, not local paths.
- Named Docker volumes are preferred over host bind mounts for server-side data.
- No remote deploy directory is required for v1.


## Proposed v1 Image Tagging and Release Logging

Image tag format:

- `vYYYY-MM-DD-<sha7>`

Tag generation rule:

- Use local date at deploy time plus the current git commit SHA
- Refuse to deploy if the working tree is dirty
- Do not derive tag uniqueness from `lexe-logs.md`

`lexe-logs.md` should record at least:

- deploy datetime
- app name
- vm host name
- image repository
- image tag
- image digest if available
- git commit SHA if available
- deploy result

`lexe-logs.md` is committed to git. It is history only, not part of tag derivation.


## Proposed v1 Healthcheck Behavior

- `healthcheck-url` is required for all apps in v1
- Healthcheck is executed from the local machine, not from inside the VM
- For non-public apps, the healthcheck may only be reachable when the developer is authenticated to
  exe.dev
- Success means HTTP status code is in the 2xx range
- Default behavior:
  - wait up to 90 seconds
  - retry every 3 seconds
- If the healthcheck does not succeed within the timeout, deploy is considered failed
- A future enhancement may detect `401` / `403` and prompt the developer to log in


## Proposed v1 Hook Execution Model

- Hooks are launched from the local machine against the remote Docker daemon using `docker run --rm` or `docker compose run --rm`
- Hook containers use the same locally hydrated env as the main app containers
- The initial implementation should support only image-based hook containers, not arbitrary host shell scripts
- Hook schema is intentionally simple in v1: `service` plus `command`


## Open Implementation Items

- Confirm the exact exe.dev public HTTP proxy commands / API needed for `public-service` exposure
- Confirm whether binding directly to 80/443 inside Docker Compose is preferable to using exe.dev HTTP proxy mapping


## Integrated Evaluation Notes

- The spec aligns closest with Kamal-style VM deploys, but keeps a smaller MVP surface.
- The biggest intentional tradeoff in v1 is stop-then-start deploys instead of proxy-mediated cutover.
- The highest-value guardrails added from evaluation are:
  - git-sha-based release tags
  - explicit compose file selection
  - local deploy locking
  - remote-docker bind-mount clarification
  - dangling-image cleanup after successful deploy


## Recommended Build Order

Config loading + validation will be built iteratively as we run into values that might come from
the config.  We should prefer convention over configuration by having sane/helpful config defaults.

1. Implement config loading + validation
2. Implement `provision`
3. Implement deploy locking + git cleanliness checks + release tag generation + local deploy log writing
4. Implement local image build + `docker pussh`
5. Implement local compose deployment flow targeting the remote Docker daemon
6. Implement hook execution
7. Implement healthcheck verification
8. Implement successful-deploy image prune
9. Implement minimal `status`


# TODO: misc

- We probably shouldn't take the config file as an argument.  We should take the path to the app
  root to deploy, from which we should be able to find the config file.  This will be important
  for things like where to run commands from when we do things like docker build / and deploy.
  - app_dpath should come from the config.  Default to the same directory as the config file but
    make it configurable.  Use a nested paths key in the yaml:
    ```
      paths:
        config: implicit, is the path to the file
        app: directory of the app, defaults to directory `paths.config` is in.
    ```

-i / --ssh-key
--no-host-key-check
SSH strict-host-key-checking configuration
