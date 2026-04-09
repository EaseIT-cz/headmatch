# TASK-114 - URL validation in fetch_curve_from_url

## Summary
Add domain allowlisting to `fetch_curve_from_url()` to prevent SSRF-like abuse when function is exposed to untrusted input.

## Context
The function currently accepts any HTTPS URL and downloads up to 5MB. The code review flagged this as a potential security risk if the function is ever exposed to untrusted input.

## Scope
- Define allowed domains (e.g., `raw.githubusercontent.com`, known measurement databases)
- Validate URL domain before download
- Add configuration option for custom domains
- Update docstring with security note
- Add tests for domain validation

## Out of scope
- Changing download size limit
- Adding authentication
- Supporting HTTP (HTTPS only remains)

## Acceptance criteria
- Only allowed domains accepted
- Clear error message for rejected domains
- Configuration for custom domains
- Tests verify validation

## Suggested files/components
- `headmatch/headphone_db.py`
- `headmatch/config.py` (for domain allowlist)
