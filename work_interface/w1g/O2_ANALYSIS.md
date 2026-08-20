# W1-G O2 — causal analysis of the structural refusal

Read-only, from frozen evidence at `50c384b`. **Nothing was run, repaired or
rerun.** W1-G architecture is treated as frozen and accepted; the capability
box, lifecycle, authority policy, validator and skill are unchanged by this
document, and no fix is proposed here.

Refusal under analysis:

```text
observed_field_not_in_source @ <work_definition>:sources.statement
' Supplier Name' claimed observed but not in fixture header
['Date','Supplier Name','InvoiceNumber','Amount','Currency','Status']
```

## 1. The fixture bytes

`work_interface/w1a/fixtures/supplier-statement.txt`, 541 bytes, pure ASCII, LF
line endings. Line 3:

```text
b'Header: Date, Supplier Name, InvoiceNumber, Amount, Currency, Status'
```

The delimiter is **comma-space** (`, `). Every column after the first is
preceded by exactly one space in the raw line. There is no leading space inside
any column name itself.

## 2. What Goose received

Delivered through `read_authorized_resource("supplier_statement")`, recovered
from O2's frozen ACP transcript:

```text
delivered chars   541
sha256 delivered  d0cb95ab5755bef3…
sha256 fixture    d0cb95ab5755bef3…
byte-identical    True
header delivered  'Header: Date, Supplier Name, InvoiceNumber, Amount, Currency, Status'
```

**No transformation occurred on the read path.** The model saw the fixture
exactly as it exists on disk. The cp1252 defect that voided the FIDELITY layer
(`CLOSURE.md` §3) is on the *input* path of the capability server and is
irrelevant here: this fixture is pure ASCII, and the value in question was
already wrong in the bytes the model **sent**.

## 3. What the model sent

From the client-side `permission_log` capture, upstream of the capability
server:

```json
"observed_fields": ["Date", " Supplier Name", "InvoiceNumber",
                    "Amount", "Currency", "Status"]
```

One field carries a leading space. **The other five do not.**

Within the same artifact, the same run, the padded token appears **exactly
once**:

```text
sources.statement.observed_fields[1]   ' Supplier Name'    <- padded
output.context_fields[1]               'Supplier Name'     <- clean
human_confirmations[5].answer          'Date, Supplier Name, and Status.'
```

## 4. The validator path

`work_definition.py:187` `_fixture_headers()`:

```python
line = line.strip()
if line.lower().startswith("header:"):
    return [c.strip() for c in line[len("header:"):].split(",") if c.strip()]
```

→ `['Date', 'Supplier Name', 'InvoiceNumber', 'Amount', 'Currency', 'Status']`

`work_definition.py:279` comparison:

```python
for f in observed_fields_by_role[role]:
    if str(f) not in headers:
        problems.append(Problem("observed_field_not_in_source", ...))
```

Membership is **exact string equality**, verified mechanically:

```text
'Supplier Name'    in headers -> True
' Supplier Name'   in headers -> False
'SupplierName'     in headers -> False
'Supplier Name '   in headers -> False
```

**The normalization is one-sided.** The validator strips its own reference
tokens (`c.strip()`); it applies no normalization whatsoever to the producer's
declared value.

## 5. Producer authority — every governing r2 instruction

```text
L48   "observed_fields": ["«exact header strings, comma-separated, in order»"]
L54   "observed_fields": ["«exact header strings»"]
L131  observed_fields must be the EXACT strings from the fixture's Header: line,
      in order. Do not normalize, merge, or rename. `Supplier Name` and
      `SupplierName` are different fields; if you write `SupplierName` when the
      header says `Supplier Name`, the artifact is refused. Read the header,
      copy each column name verbatim.
L168  find the `Header:` line, and record the column names verbatim
L222  Do not normalize or "fix" field names. Copy header strings verbatim.
```

### Is whitespace trimming specified?

```text
explicitly required     NO
explicitly forbidden    NO — but see the tension below
mechanically derivable  PARTIALLY, and only for this one field
unspecified             YES, as a general rule
```

Mechanical search of the frozen r2 skill:

```text
'whitespace'   0 hits      'strip'       0 hits      'delimiter'  0 hits
'trim '        0 hits      'padding'     0 hits      'tokeni…'    0 hits
```

The skill never states how a column name is delimited from its padding.

**Partially derivable, for this field only:** r2 displays the correct token
twice, in backticks, in the rename counterexample — `Supplier Name`, with no
leading space. A producer attending to that line has the right answer for this
specific field handed to it. There is no worked `observed_fields` example with
real values anywhere in r2; both occurrences are `«placeholders»`.

**The tension:** the only operation that converts the raw inter-comma substring
`" Supplier Name"` into the accepted `"Supplier Name"` is *stripping* — and the
skill twice instructs "do not normalize" and "copy verbatim". A producer that
reads "verbatim" maximally, treating the raw substring between delimiters as the
name, is following the stated instruction into a refusal. The counterexample
that disambiguates concerns **renaming** (`SupplierName` vs `Supplier Name`), a
different failure mode than delimiter padding.

### Is the producer ever shown the validator's rule?

**No — and it is actively prohibited.** `_fixture_headers`'s `c.strip()` appears
nowhere in r2, and every W1-G prompt forbids inspecting
`work_interface\work_definition.py`. The producer cannot discover the one-sided
normalization by any authorized route.

## 6. Cross-run comparison — source-field declarations only

```text
run  statement.observed_fields                                            padded?
O1   ["Date","Supplier Name","InvoiceNumber","Amount","Currency","Status"]   no
O2   ["Date"," Supplier Name","InvoiceNumber","Amount","Currency","Status"]  YES
O3   ["Date","Supplier Name","InvoiceNumber","Amount","Currency","Status"]   no

ledger.observed_fields — byte-identical across O1/O2/O3, none padded
```

**O2 alone retained delimiter-adjacent whitespace**, on one field, from input
that was byte-identical in all three runs.

## 7. Classification

```text
proximate cause:      PRODUCER_ERROR
architectural cause:  SKILL_UNDERSPECIFICATION
```

### Why PRODUCER_ERROR

The refusal is caused by a value the model emitted, and nothing downstream of it
altered that value. The evidence excludes every mechanical explanation:

- **Not a parsing rule.** A split-on-`,`-without-strip would pad *five* fields.
  Exactly one is padded.
- **Not a consistent reading of "verbatim".** The same model, in the same
  artifact, wrote the clean token in `output.context_fields` and inside the
  verbatim human answer. It applied no such interpretation anywhere else.
- **Not input variance.** The fixture reached all three runs byte-identical.
- **Not infrastructure.** The value was already padded in the client-side
  capture, upstream of the capability server, and the encoding defect cannot
  touch ASCII.

An isolated, non-systematic transcription slip in one of six tokens.

### Why SKILL_UNDERSPECIFICATION

r2 never states the tokenization rule that governs the field it makes
load-bearing. It demands "EXACT strings" and "verbatim" copying from a
`, `-delimited line without ever defining where the name begins. Correctness for
this particular field is recoverable only from an incidental backticked token in
a counterexample about a *different* failure mode; for any header not
exemplified in the skill, the rule is simply absent.

### Why not VALIDATOR_CONTRACT_MISMATCH

A real asymmetry exists and is worth recording: the validator normalizes its own
side and exact-matches the producer's, while instructing the producer not to
normalize — so the operation required for acceptance is the one the skill
forbids by name. I did not classify this as the primary architectural cause
because:

- the validator is internally consistent, and its strictness is deliberate and
  documented in its own docstring ("`Supplier Name` and `SupplierName` are
  different strings… that is the point");
- "column name" conventionally excludes delimiter padding, and 2 of 3 runs
  reached the accepted form from identical input, so the contract is satisfiable
  as written;
- the gap is that the skill never *states* the rule, not that the validator
  demands something contradictory.

The asymmetry is a **latent contributing condition**, not the cause of this
refusal. It would become the primary cause for a header whose correct
tokenization the skill does not incidentally display.

## 8. Recorded, not acted on

The corrected UTF-8 capability server (`059cbd4`) has **not** been exercised by
any pack. `FIDELITY 3/3` for W1-G is a **recomputation** from the bytes the model
sent, not a measured result. Claiming a measured `FIDELITY 3/3` requires a fresh
pack run on the fixed server. W1-G is not to be rerun for this.

No fix is proposed. Classification is complete; remedy is a separate decision.
