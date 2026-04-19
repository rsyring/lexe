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
