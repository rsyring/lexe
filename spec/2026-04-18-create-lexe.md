# Spec for lexe

`lexe` is a cli tool used to manage exe.dev VMs and deploy apps to those vms.


## References

- [exe.dev docs](https://exe.dev/llms.txt)
- [unregistry repo](https://github.com/psviderski/unregistry)
- `~/projects/doist-pkg/tasks/doist-server`: existing deployment script that can be reviewed for
  patterns/ideas
- `~/projects/code-examples/configs/juke-config.py`: for app config file processing example


## App / VM Setup

- Each app gets it's own VM
- If VM doesn't exist, create it
- Do some basic VM prep like turning on automatic updates (details TBD)
- If public, use exe.dev ssh commands to make VM's web app publically accessible
- Make the app's HTTP(S) port(s) the default ones for the VM


## App Deployments

- Dockerfile for the deployable container
- Docker Compose
    - compose.yaml: base file shared by local and remote
    - compose.server.yaml: used explicitly with deploy logic
    - compose.override.yaml: for local dev, automatically used by docker compose
- Build docker image in local registery
    - Tag each unique build so we can target it as part of the deploy
- Use unregistry to transfer image to remote
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

Every app will get a 1password service account.  We will use the op cli (which we need to install as part of our provision) to hydrate a .env template file.

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

Let's use `v{year}-{month}-{day}-{count}`.  Count increments if we do more than one deploy a day.

- Should `lexe deploy` always build locally, or should it also support deploying an already-built
  image tag?

    - Build locally, which should be really fast if already built and no changes
    - use `unregistry`'s docker integration to sync the image to the remote server


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
- Secrets are hydrated locally using a 1Password service account and `op run --env-file`, then passed to remote containers via the Docker API at container create/run time.
- VM identity is provided explicitly by config via `vm-host-name`.
- `provision` is idempotent and is responsible for bringing the VM into conformance.
- Deploys build locally, sync the built image to the VM via unregistry / `docker pussh`, and then manage remote containers from the local machine by targeting the remote Docker daemon.
- Successful deploy means a configured healthcheck URL returns a 2xx status code.
- Pre-start hooks abort deploy on failure. Post-start hooks are report-only.
- Output should be human-readable.
- Deploy history should be recorded in `lexe-logs.md`.
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
- `secrets.env`: local env template with 1Password references consumable by local `op run --env-file`
- `lexe-logs.md`: append-only local deploy log written by `lexe`


## Proposed `lexe.yaml` Schema

We'll define the config as we need it otherwise it's probably YAGNI.

## Proposed v1 Command Contract

### `lexe provision`

Responsibilities:

- Validate `lexe.yaml`
- Ensure the target VM exists; create it if not
- Assume the VM is reachable over SSH
- Ensure the Docker Engine is installed and usable on the VM
- Validate local prerequisites needed to target the remote Docker daemon:
    - Docker CLI
    - Docker Compose plugin
    - `docker pussh`
    - `op` CLI
    - SSH access to the VM
- Ensure VM-level configuration required by the app is present
- If it's a public service, configure public HTTP exposure for the selected app service

Behavior:

- Idempotent: safe to re-run
- If the VM exists but is partially configured, attempt to repair it
- If a configured VM name is invalid or conflicts, surface the error to the user and stop


### `lexe deploy`

Responsibilities:

- Validate `lexe.yaml`
- Build the app image locally
- Generate a release tag in the form `vYYYY-MM-DD-N`
- Tag the built image with the computed release tag
- Push the image directly to the remote VM with `docker pussh`
- Run local `docker compose` against the remote Docker daemon using local compose files
- Hydrate secrets locally with `op run --env-file` before creating or replacing remote containers
- Stop and replace running services on the remote VM via the remote Docker daemon
- Run configured pre-start hooks as one-off containers on the remote VM via the remote Docker daemon
- Run configured post-start hooks the same way after startup
- Check `healthcheck-url` from the local machine until success or timeout
- Append a deploy record to `lexe-logs.md`

Behavior:

- `deploy` does not implicitly create the VM. User runs `provision` first.
- If local or remote prerequisites are missing, fail with a clear error.
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
- `lexe` targets the remote VM's Docker daemon from the local machine.
- Compose files remain local and are evaluated locally by Docker Compose.
- `secrets.env` remains local and is hydrated locally by `op run --env-file`.
- Hydrated secret values are sent to the remote Docker daemon as part of container configuration.
- Secret values are not baked into the image; they are attached to running containers at deploy time.
- No remote deploy directory is required for v1.


## Proposed v1 Image Tagging and Release Logging

Image tag format:

- `vYYYY-MM-DD-N`

Tag generation rule:

- Use local date at deploy time
- Read `lexe-logs.md`
- Count existing deploy entries for that date
- Next deploy for that date uses `count + 1`

`lexe-logs.md` should record at least:

- deploy datetime
- app name
- vm host name
- image repository
- image tag
- image digest if available
- git commit SHA if available
- deploy result


## Proposed v1 Healthcheck Behavior

- `healthcheck-url` is required for public apps
- Healthcheck is executed from the local machine, not from inside the VM
- Success means HTTP status code is in the 2xx range
- Default behavior:
  - wait up to 90 seconds
  - retry every 3 seconds
- If the healthcheck does not succeed within the timeout, deploy is considered failed


## Proposed v1 Hook Execution Model

- Hooks are launched from the local machine against the remote Docker daemon using `docker run --rm` or `docker compose run --rm`
- Hook containers use the same locally hydrated env as the main app containers
- The initial implementation should support only image-based hook containers, not arbitrary host shell scripts
- Hook schema is intentionally simple in v1: `service` plus `command`


## Open Implementation Items

- Confirm the exact exe.dev public HTTP proxy commands / API needed for `public-service` exposure
- Confirm whether binding directly to 80/443 inside Docker Compose is preferable to using exe.dev HTTP proxy mapping
- Decide whether any deploy metadata beyond `lexe-logs.md` is needed, or whether container labels are sufficient
- Decide whether `lexe-logs.md` should live at repo root or under a dedicated `.lexe/` directory
- Decide whether non-public apps require a healthcheck URL in v1 or may omit it


## Recommended Build Order

Config loading + validation will be built iteratively as we run into values that might come from
the config.  We should prefer convention over configuration by having sane/helpful config defaults.

3. Implement `provision`
4. Implement release tag generation + local deploy log writing
5. Implement local image build + `docker pussh`
6. Implement local compose deployment flow targeting the remote Docker daemon
7. Implement hook execution
8. Implement healthcheck verification
9. Implement minimal `status`
