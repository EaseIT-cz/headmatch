# TASK-070 — Fix shelf Q/S inconsistency in CamillaDSP export

## Summary
The PEQ fitter stores the RBJ shelf slope parameter `S` (clamped [0.1, 1.0]) in `PEQBand.q` for lowshelf/highshelf filters. CamillaDSP interprets the `q` field as true Q, not slope S. The values are related but not equal at S=0.7.

## Scope
- In the CamillaDSP exporter, convert shelf `S` to the equivalent Q before writing.
- Alternatively, store the correct Q in the fitter and convert to S only for the RBJ coefficient computation.
- Add a test asserting that exported CamillaDSP shelf Q values differ from the raw S value stored internally.

## Suggested files
- `headmatch/peq.py`
- `headmatch/exporters.py`
- `tests/test_peq_exporters.py`
