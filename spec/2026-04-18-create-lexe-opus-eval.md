
# Evaluation

Evaluation of this spec against similar tools (Kamal, Dokku, CapRover, fly.io `fly deploy`, raw
`docker context` workflows), small-scale deployment best practices, and internal consistency.

## Closest analog: Kamal

The design overlaps heavily with 37signals' Kamal (v2). Useful reference points:

- Kamal also targets plain VMs with Docker, uses SSH-based remote daemons, ships secrets as env,
  runs pre/post hooks, and uses healthchecks to gate cutover.
- Kamal uses a Traefik/`kamal-proxy` sidecar to do near-zero-downtime rollouts by starting new
  containers, waiting for health, then swapping. This is the single biggest gap vs. `lexe`'s
  stop-then-start model. For a solo project it's acceptable, but the pattern is cheap to adopt
  later: run the new compose stack under a suffixed project name, flip the proxy, then `down` the
  old project. Worth calling out as a known future path rather than leaving it implicit.
- Kamal stores config in one file (`config/deploy.yml`) and pins accessories (DBs, workers) as
  first-class entries. `lexe.yaml`'s "define as we go" approach will likely converge on the same
  shape; Kamal's accessory model is a reasonable template.
- Kamal does not use unregistry; it pushes to a registry. Using `docker pussh` is a legitimate
  simplification for single-VM, single-deployer setups and removes a moving part.

Net: `lexe` is essentially a smaller, opinionated Kamal minus the proxy-based cutover and minus
the registry. That is a defensible MVP.

## Strengths

- Scope and non-goals are explicit, which is the single most important thing in a tool like this.
- Idempotent `provision` separated from `deploy` is the right split.
- Secrets via 1Password service account + `op run --env-file` is a good fit for solo ops: no
  secret state stored in the tool, no secret state in the image, no remote secret store to manage.
- Image transfer via `unregistry`/`docker pussh` avoids standing up a registry for a use case that
  doesn't need one.
- Healthcheck gating deploy success (2xx, timeout, retry interval) is the right definition of
  "done".
- Hooks constrained to image-based containers (not host shell) avoids the classic escape hatch.
- Recording deploy history at all (`lexe-logs.md`) puts you ahead of most hand-rolled scripts.

## Concerns worth addressing before implementation

1. **Release tag counter is fragile.** Deriving `N` in `vYYYY-MM-DD-N` by counting entries in
   `lexe-logs.md` couples tag generation to a mutable, human-editable markdown file. Problems:
   lost/edited file resets the counter; concurrent deploys race; git merges across machines
   corrupt the count. Prefer one of:
   - `vYYYY-MM-DD-HHMMSS` (no counter, no state needed), or
   - derive `N` from existing image tags on the remote daemon (`docker image ls`), or
   - append `+<short-sha>` so the tag is unique even if the counter collides.
   Also log the git commit SHA in the tag itself, not only in `lexe-logs.md`, so the image is
   self-describing.

   **Decisions:**
   - Tag format is `vYYYY-MM-DD-<sha7>` using the current git commit SHA. No counter, no state
     file, no remote tag inspection.
   - `lexe deploy` fails fast if the working tree is dirty. No `-dirty` suffix, no bypass flag
     in v1.
   - If the computed tag already exists on the remote daemon, the default behavior is a no-op:
     skip build, skip pussh, skip stop/start, skip hooks, skip healthcheck. Report clearly that
     the commit is already deployed.
   - `lexe deploy --force` overrides the no-op path: it still skips build+pussh when the image
     is already present (nothing to rebuild), but runs stop/start, hooks, and healthcheck. This
     covers secret rotation and retry-after-failure.
   - When the image is *not* already present on the remote, `--force` is a no-op relative to
     default behavior (normal deploy runs either way).

2. **`compose.override.yaml` is a foot-gun for deploys.** Docker Compose auto-loads
   `compose.override.yaml` whenever `-f` is not specified. Any `lexe deploy` codepath must
   explicitly pass `-f compose.yaml -f compose.server.yaml` (and nothing else) to guarantee the
   dev override never leaks into production. Call this out in the execution model.

3. **Remote Docker daemon targeting needs a constraint on bind mounts.** Because compose is
   evaluated locally but executed against the remote daemon, any `volumes:` entry using a
   host path resolves on the *remote* filesystem, not the local one. This surprises people. Spec
   should state: "Host bind mounts in `compose.server.yaml` refer to paths on the VM. Named
   volumes are preferred." Also specify that the remote daemon is reached via
   `DOCKER_HOST=ssh://...`, not TCP.

4. **Ubuntu 24.04 provisioning is under-specified for a public VM.** Automatic updates alone is
   thin. At minimum for a box exposing 80/443: enable `ufw` with a default-deny policy and
   allow-list the needed ports, and set a non-root user for SSH. You mention existing scripts
   handle this — fine, but the spec should name what `provision` is responsible for vs. what is
   assumed pre-done, so the boundary is clear.

5. **Image retention on the VM.** Every deploy leaves another tagged image on the remote daemon.
   Add a simple retention step to `deploy` (e.g. keep last 5 tags for the app's repo, prune the
   rest) or it will silently fill the disk on small VMs.

   **Decision:** run `docker image prune --force` at the end of each successful deploy. This
   clears dangling layers from rebuilds (the real churn) without removing prior tagged releases,
   so manual rollback to a previous tag remains possible. Do **not** use `-a`, which would
   remove unused tagged releases. A "keep last N tags" pass can be added later if needed.

6. **Concurrent deploy protection.** A simple local lock file (e.g. `flock` on `.lexe/deploy.lock`)
   prevents two terminals from racing. Cheap and avoids a whole class of weird states.

   **Decision:** use `flock` on `lexe-deploy.lock`.

7. **`lexe-logs.md` committed vs. ignored is unresolved.** This matters now, not later:
   - Committed: merge conflicts on counter, but history is shared across machines.
   - Ignored: no cross-machine history, counter desyncs between machines.
   Decision point: if you switch to a timestamp-based tag (#1), the file can be git-ignored
   without penalty, and that's likely the cleanest outcome. The open item
   ("repo root vs. `.lexe/`") should be resolved together with this.

   **Decision:** `lexe-logs.md` is committed. The counter-collision concern is moot because
   tags are now `vYYYY-MM-DD-<sha7>` (#1), so the log file has no derived state — it is purely
   an append-only history and merges cleanly across machines.

8. **`secrets.env` is misnamed.** The file described is a 1Password *template* with `op://`
   references, not secrets. Calling it `secrets.env` invites someone to commit real secrets into
   it later. Recommend `secrets.env.1p` or `.env.tpl` and document that it is safe to commit.

   **Decision:** the env template path is `deploy/env` by default and is configurable in
   `lexe.yaml` so multiple environments (e.g. `deploy/env.staging`, `deploy/env.prod`) can each
   point at their own template. The file holds `op://` references, is safe to commit, and is
   hydrated at deploy time via `op run --env-file`.

9. **VM identity by host name only.** exe.dev presumably has a stable VM ID behind the host name.
   Caching that ID (e.g. in `.lexe/vm.json`, git-ignored) lets `provision`/`deploy` detect a
   rename or a recreated-VM-with-same-name case and fail loudly instead of silently deploying to
   a different machine.

   **Decision:** deferred. Not a concern for MVP.

10. **Rollback posture.** "Let the dev figure it out" is acceptable for MVP, but the previous
    image tag is already on the VM (until pruned). Document the one-line manual rollback
    (`docker compose ... up -d` with `IMAGE_TAG=<prev>`) so the dev isn't improvising under
    pressure.

    **Decision:** deferred. Not in MVP scope.

## Internal consistency issues

- "Recommended Build Order" starts at item 3; items 1 and 2 are missing.
- "Proposed `lexe.yaml` Schema" is a section header with no content and a YAGNI note. Either
  drop the header or add a single line listing the fields already implied by the rest of the
  spec (`app-name`, `vm-host-name`, `public-service`, `healthcheck-url`, `hooks.pre-start`,
  `hooks.post-start`). Leaving a stub header reads as an oversight.
- Healthcheck requirement: spec says `healthcheck-url` is "required for public apps" but an open
  item still asks whether non-public apps need it. Resolve or the schema is ambiguous on day one.
- `provision` lists "Assume the VM is reachable over SSH" alongside "Ensure the target VM
  exists; create it if not." If `provision` creates the VM, it is also responsible for the first
  SSH reachability check (including host key acceptance), not just assuming it. Tighten the
  wording.
- The spec alternates between `docker pussh` and "unregistry". They're the same thing; pick one
  term and use it consistently.

## Best-practice alignment summary

| Area | Status |
|---|---|
| IaC / reproducible provisioning | Good (idempotent `provision`) |
| Immutable build artifacts | Mostly — strengthen tag uniqueness (#1) |
| Secret separation from image | Good |
| Least-privilege remote access | Under-specified (SSH transport, user, ufw) |
| Observability | Minimal, acceptable for MVP |
| Failure recovery | Deferred; document manual rollback recipe |
| Config-as-data in repo | Good |
| Concurrency safety | Missing local lock |
| Disk/state hygiene on VM | Missing image retention |

## Bottom line

The spec is coherent and the scope is honest. The highest-leverage fixes before writing code are:
(1) make release tags self-sufficient and drop the markdown-derived counter, (2) lock down the
compose file selection so the dev override can never leak, (3) tighten provision's
responsibility boundary for a public Ubuntu VM, and (4) resolve the `lexe-logs.md` location and
commit policy. Everything else can be iterated on safely.
