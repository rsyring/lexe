# Spec for `lexe provision` / `lexe destroy`

## Checklist

- [x] Add `lexe.provision.Provision` as the provision command entry point
- [x] Wire `lexe provision` so the CLI instantiates `Provision` from matching init args
- [x] Add the minimum config model and file loading needed for the provision step
- [x] Add `lexe destroy` as the destroy command entry point
- [x] Wire `lexe destroy` so the CLI instantiates `Destroy` from matching init args
- [x] Define the exe.dev VM existence/create/update workflow
- [x] Define SSH reachability checks after VM create/update
- [x] Define Docker install/verification behavior on the VM
- [x] Define local prerequisite checks required before provision runs
- [x] Define how `public-service` maps to exe.dev public exposure behavior
- [x] Define destroy behavior for existing vs missing VMs
- [x] Validate the hello example through a full provision/destroy lifecycle
- [ ] Define how existing Ubuntu 24.04 setup/hardening scripts plug into provision

## References

- Parent spec: `spec/2026-04-18-create-lexe.md`

## Current Scope

This spec is only for VM lifecycle commands: `provision` and `destroy`.

For now, the implemented config surface is intentionally narrow and only covers:

- `app-name`
- `vm-host-name`
- `public-service`

## Decisions Captured

- `vm-host-name` is the single VM identity used by both `provision` and `destroy`.
- `provision` is idempotent for an existing VM and continues to verify SSH reachability and Docker.
- `destroy` is idempotent: if the VM is already absent, it reports that state and exits successfully.
- `public-service` only affects `provision`; `destroy` simply removes the whole VM.
- Provision currently relies on the underlying tooling to surface missing local command failures directly.
- Ubuntu 24.04 host setup/hardening scripts are still deferred.

## Validation Notes

- Confirmed the exe.dev help surface needed for provision and destroy, including VM deletion.
- Verified the real `examples/hello` lifecycle end-to-end: destroy existing VM, confirm absence,
  provision again, confirm presence, then destroy again.


