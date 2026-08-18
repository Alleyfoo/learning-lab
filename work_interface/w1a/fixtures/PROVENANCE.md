# W1-A frozen fixture set — provenance

The W1-A fixture set is a **byte-for-byte copy** of the W0 reconciliation case
frozen evidence, so the W1-A runs are graded against the same sample inputs the W0D
validator was calibrated to. Reusing the W0 case is deliberate: the validator's
`observed_fields` cross-check is already honest against these exact headers, and the
W0B corrected candidate (`work_interface/cases/W0B_corrected.json`) is the known-good
oracle for what a passing run should resemble.

## Files

| File | sha256 | Source (W0B frozen evidence) |
|---|---|---|
| `supplier-statement.txt` | `d0cb95ab5755bef320390f11899c53034548a60678e27430882e556ce1a45feb` | `work_interface/evidence/W0B_fixtures/supplier-statement.txt` |
| `ledger-book.txt` | `284861d7d948dd6f0cd3a5e7826a6794d15db0ce2aafe108dafa37752c36f25e` | `work_interface/evidence/W0B_fixtures/ledger-book.txt` |

## Discipline

- **Do not edit these files.** If a run appears to fail because of a fixture, the
  fixture is not the thing to change — the run is the thing under test.
- The grader (`work_interface/w1a/grade.py`) resolves each run's `sources.<role>.fixture`
  basename against this directory (`evidence_dir`). A run that claims an
  `observed_fields` entry not present in the header here is refused for
  `observed_field_not_in_source` — e.g. `SupplierName` vs the real header `Supplier Name`.