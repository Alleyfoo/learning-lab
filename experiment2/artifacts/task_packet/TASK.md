# Task

## Business objective

Recurring sales data arrives from partners. Every file below reports the same kind of business
information: **how much of each product was sold, in which country, in which month.**

The files do not agree on how to say it. They differ in shape, language, naming, and local
conventions. They will keep differing, and new partners will send forms you have not seen.

Your job is to produce a **reusable executable procedure** that turns such a file into the
canonical form below. Not one converted file — a procedure that keeps working on later files
of the same kind, run by ordinary software with no model involved.

## Required canonical output

A `pandas.DataFrame` with exactly these columns:

| column | meaning | form |
| --- | --- | --- |
| `country` | the country the sales belong to | two-letter uppercase code |
| `product_id` | the product | as issued by the business, e.g. `ART-0001` |
| `period` | the calendar month | `YYYY-MM` |
| `sales` | the sales value | number, 2 decimal places |

Grain: **one row per (country, product_id, period).**

## Interface

Submit a single Python module defining:

```python
def normalize(source_path: str) -> pandas.DataFrame:
    ...
```

`contract.py` (in this directory) provides two exceptions:

- `Escalate(reason, details)` — raise when the source **cannot** be normalized on the evidence
  available in it. Correct escalation is a success.
- `AskHuman(question, why_not_inferable)` — raise when a human must supply information that is
  **not present in the source**. Every use is recorded and reviewed.

Your module may import anything in the standard library plus `pandas` and `numpy`. It may not
read anything outside the file it is given.

## Sources

`sources/` contains example files. They are not the only files your procedure will face.

## How the result is judged

- Output is compared to hidden ground truth on rows, identities, periods, values and grain.
  Appearance is not evidence.
- Your procedure is run against files you have not seen, including ones using conventions
  absent from every example here.
- It is also run against later files of the same kinds, unchanged, with no model involved.
- Some inputs cannot be resolved from their own contents. Normalizing those anyway is the worst
  outcome recorded. Escalating something that was in fact resolvable is also counted, separately.
- Asking a human for something the file already contains counts against the procedure. So does
  inventing something the file does not contain.

A procedure that converts every example correctly and generalizes to nothing has not
succeeded at the task.
