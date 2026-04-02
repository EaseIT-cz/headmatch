# TASK-038 — Document and surface the new diagnostics path

## Summary
Make the new `headmatch doctor` command visible in the README and other beginner-facing guidance so users know it exists before they get stuck.

## Context
HeadMatch now has a first CLI diagnostics command, but it will not reduce support friction if users do not discover it. The next small ergonomics step is to thread that command into onboarding and troubleshooting guidance.

## Scope
- Update README and beginner-facing guidance to mention `headmatch doctor`.
- Add the command where it is most useful in setup/troubleshooting flows.
- Keep the wording simple and practical.
- Update tests only if needed.

## Out of scope
- New diagnostics features.
- Packaging changes.
- GUI diagnostics workflow.
- Broad docs rewrite.

## Acceptance criteria
- README clearly mentions `headmatch doctor` in an appropriate setup/troubleshooting context.
- Beginner-facing guidance points users to the command when setup is uncertain.
- The change is small, clear, and consistent with the current product strategy.

## Suggested files/components
- `README.md`
- `docs/architecture.md` if needed
- `headmatch/cli.py` only if a small copy tweak helps discovery
