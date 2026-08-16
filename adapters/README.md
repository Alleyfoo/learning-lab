# Input adapters

An adapter turns a file into the collection shape everything else already
consumes. It adds **no task semantics**. Downstream, nothing knows the data came
from a spreadsheet.

```text
workbook.xlsx --> {"order_lines": [...], "price_list": [...]}
```

## xlsx

`python adapters/xlsx.py <book.xlsx> <specs.json> [outdir]`

Which sheet becomes which collection is **declared**, never guessed:

```json
[{"sheet": "Order lines", "collection": "order_lines", "header_row": 1}]
```

Every value conversion is declared and none of them tidies — see the module
docstring. The one worth repeating: a float becomes `repr(value)`, the shortest
decimal that reads back as the same double, so `19.99` stays `"19.99"` and is
exactly computable with `Decimal` downstream.

It refuses rather than guesses: blank headers over data, duplicate headers,
missing sheets, empty sheets, uncalculated formulas. An adapter that guesses
puts a wrong number into a deterministic pipeline that is then faithful to it
forever.

`openpyxl` is imported on use, so a fleet without a workbook worker does not
need it installed.
