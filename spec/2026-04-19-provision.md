# Spec for `lexe provision`

## Checklist

- [x] Add `lexe.provision.Provision` as the provision command entry point
- [x] Wire `lexe provision` so the CLI instantiates `Provision` from matching init args
- [x] Add the minimum config model and file loading needed for the provision step
- [ ] Confirm the exact `lexe.yaml` fields required for initial VM create/update behavior
- [ ] Define the exe.dev VM existence/create/update workflow
- [ ] Define SSH reachability checks after VM create/update
- [ ] Define Docker install/verification behavior on the VM
- [ ] Define local prerequisite checks required before provision runs
- [ ] Define how `public-service` maps to exe.dev public exposure behavior
- [ ] Define how existing Ubuntu 24.04 setup/hardening scripts plug into provision

## References

- Parent spec: `spec/2026-04-18-create-lexe.md`

## Current Scope

This spec is only for `provision`.

For now, the implemented config surface is intentionally narrow and only covers:

- `app-name`
- `vm-host-name`
- `public-service`

## Notes

- The config loader currently supports only top-level `key: value` entries needed by provision.
- We can expand the parser and schema as provision behavior becomes more concrete.

## Questions

- Did you mean `spec/2026-04-18-create-lexe.md` when you referenced
  `spec/2026-04-18-create-lexe-spec.md`? That exact file is not currently in the repo.