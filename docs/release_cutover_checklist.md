# Web parity release & cutover checklist

This checklist defines the auditable release path for removing desktop dependency and cutting over to the web workflow.

## How to use this document

Use this document as **release-time guidance and approval criteria**. It is not intended to block routine implementation tasks that do not change release status or claim parity completion.

For normal feature work:
- use the checklist to understand target evidence and release expectations;
- apply the relevant parts when you are changing parity status, cutover readiness, or release claims;
- do not treat every item here as a mandatory prerequisite for unrelated bug fixes, refactors, or scoped feature work.

## Source of truth

- Product parity backlog: `docs/web_desktop_parity_checklist.md`
- Machine-readable status map: `.github/backlog-status.json`
- CI gate that validates row evidence + cutover prerequisites: `.github/workflows/parity-evidence.yml`
- Enforcement script: `scripts/verify_parity_backlog.py`

## Status transitions (auditable workflow)

Apply this section when a task status is being advanced in the parity backlog, especially when moving to `Done`.

1. Keep each task row status synchronized in two places:
   - Human-readable status in `docs/web_desktop_parity_checklist.md`
   - Machine-readable status in `.github/backlog-status.json`
2. Do **not** mark a task `Done` unless all required evidence entries in `.github/backlog-status.json` are present and valid:
   - `endpoint_contract_files`
   - `api_test_commands`
   - `ui_test_commands`
   - `contract_check_commands`
3. Every contract check command should call a `web/scripts/check-*-contract.mjs` script.
4. CI should stay green for any task marked `Done`, including its API test, UI test, and contract checks.
5. CI should also run `npm --prefix web run test:ui-regression` whenever any task is `Done`, because that is part of release/cutover confidence.

## Release gate checklist

Before release/cutover approval:

- [ ] All tasks in `.github/backlog-status.json` are mapped 1:1 to checklist IDs in `docs/web_desktop_parity_checklist.md`.
- [ ] Every task includes endpoint contract evidence + API test command + UI test command + contract check command.
- [ ] Contract checks pass (`web/scripts/check-*-contract.mjs` commands).
- [ ] For every `Done` task, mapped API/UI evidence checks pass.
- [ ] `npm --prefix web run test:ui-regression` passes as a prerequisite when `Done` tasks exist.
- [ ] No desktop-only fallback is required for any task marked `Done`.

## Change-control notes

For parity-status changes or cutover-oriented PRs, include in the PR description:

- Task ID(s) changed
- Previous status → new status
- Contract check command(s) run
- API/UI test command(s) run
- CI run URL proving gate success

This process makes status transitions traceable and reviewable without turning the checklist into a blanket implementation blocker.
