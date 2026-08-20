# W1-G closure — additive

Evidence commit `50c384b`. Pack frozen at `a1ce00a`; `PROMPT.md` and `SKILL.md`
byte-identical before and after, controlled-input hashes unchanged. **Nothing in
`runs/` was edited, repaired, or rerun.** Where a reporter is wrong, the
correction lives here.

## Result by layer

```text
RESOURCE DISCOVERY      3/3   both verbs found and used, unprompted
RESOURCE CONSUMPTION    3/3   skill + supplier_statement + ledger_book
ARTIFACT PRODUCTION     3/3   write_work_definition invoked
AUTHORITY               3/3   CLEAN
STRUCTURAL              2/3   PASS  (O2 refused, worker-caused)
FIDELITY                0/3   as reported -> VOID, see §3 (corrected: 3/3 clean)
```

## 1. The capability box works

Every run, identically: **four capability calls, two turns, no continuations, no
denials, no shell.**

```text
ALLOW READ   resource_id=skill
ALLOW READ   resource_id=supplier_statement
ALLOW READ   resource_id=ledger_book
ALLOW WRITE  content=~3.3k chars
-> COMPLETED: artifact written; session terminated immediately
```

Against the same prompt, same model, same lifecycle:

```text
        turns  perm reqs  denials  shell  artifact
W1-F      13      8-9        0-1     0-1    0/3
W1-G       2        4          0       0    3/3
```

Neither verb is named anywhere in the prompt — the worker discovered both and
used each exactly as many times as the task required. The prompt still carries
W1-F's stale Windows-safe shell hints, deliberately unedited, and the worker
ignored them: there was no shell to reach for, and it did not invent one (unlike
W1-F's N3, which fabricated a `powershell` tool name).

The confounder identified in `../w1f/POST_CLOSURE.md` is gone, so this is the
first artifact-production result in this line that measures the worker rather
than the harness.

## 2. STRUCTURAL — 2/3 PASS, and O2's refusal is real

```text
O1  PASS      sha256 fabd167cbf79
O2  REFUSED   observed_field_not_in_source
O3  PASS      sha256 67358d055d7f
```

O2 claimed `" Supplier Name"` — with a **leading space** — as an observed field
of the statement source. The fixture header is `Supplier Name`. This is a
transcription artifact of splitting a comma-separated header without stripping,
and it is **worker-caused**: the leading space is present in the bytes the model
sent, verified from the client-side `permission_log` capture, upstream of every
part of the infrastructure defect in §3.

Confirmed unaffected by that defect — the validator returns identical verdicts
on the bytes the model sent and the bytes on disk:

```text
run   on-disk                          as-sent
O1    valid=True   []                  valid=True   []
O2    valid=False  [observed_field…]   valid=False  [observed_field…]
O3    valid=True   []                  valid=True   []
```

**STRUCTURAL stands as reported.** The instrument caught a genuine fidelity
error in field transcription, which is exactly its job.

## 3. FIDELITY — VOID as reported (my infrastructure defect)

`FIDELITY.md` reports `FID-3 PHANTOM_CONFIRMATION` on the source-of-truth
confirmation in **all three** runs. A uniform failure across every run is a
signature of the instrument, not the subject, and it is:

`authorized_capabilities.py` read its stdio JSON-RPC stream as
`for line in sys.stdin`, and **`sys.stdin.encoding` is `cp1252` on this
machine**. Goose sends UTF-8. The em dash in canonical block row 3 arrived as
`E2 80 94`, was decoded as three cp1252 characters, and was re-encoded on write:

```text
model sent   b'Neither \xe2\x80\x94 bo'                    U+2014, correct
on disk      b'Neither \xc3\xa2\xe2\x82\xac\xe2\x80\x9d '  double-encoded
```

The worker transmitted the answer **verbatim and correctly**. The corruption is
entirely mine, downstream of the model, inside the capability server.

Reads were unaffected because responses go out through `json.dumps`, which
escapes non-ASCII by default — which is also why the frozen-r2 hash check in
calibration `a1ce00a` passed and did not expose this. The defect is on the
**input** path only, and only bites on non-ASCII content.

Corrected reading, recomputed here with the frozen instrument against the bytes
the model actually sent — a recomputation from frozen evidence, **not a rerun**:

```text
run   as reported (on disk)        corrected (as sent)
O1    1 finding  FID-3             0 findings
O2    1 finding  FID-3             0 findings
O3    1 finding  FID-3             0 findings
```

**Corrected FIDELITY: 3/3 clean, zero findings.** Every confirmation maps to its
canonical row; there are no phantom confirmations. `FIDELITY.md` is left exactly
as produced.

Fixed for future packs, with an offline regression, in the commit following this
one. `authorized_reader.py` shares the defect on its input path and is **left
untouched**, because it is frozen W1-F evidence.

## 4. What may not be claimed

- N=3, one model, one fixture pair. **No population-level reliability claim.**
- The corrected 3/3 fidelity is a **recomputation**, not a measured result. It
  says the worker's transmitted bytes were faithful; a clean measured 3/3 would
  require a future pack run on the fixed server.
- 2/3 structural PASS is a small-N observation about one transcription failure
  mode, not a pass rate.
- Discovery is established for **this** two-verb shape, not for MCP tools
  generally.

## 5. What this establishes

The architectural claim holds. Given exactly the verbs its role needs, this
worker completed the definition task end to end in two turns, stayed inside the
capability box without a single denial, consumed every authorized resource, and
produced a structurally valid artifact in 2 of 3 runs — with the one failure
being a real, specific, observable content error rather than an infrastructure
artifact.

Manager owns the world; worker gets a few verbs. The remaining failure is now
about **what the worker wrote**, which is the question the lab wanted to ask.

## 6. Next variable — one only

Do not rerun W1-G. Fix the encoding defect (next commit), and let the next pack
measure fidelity cleanly rather than by recomputation. The open worker question
is O2's unstripped header field: whether that is stable, and whether the skill
should say anything about verbatim field transcription — a **skill-content**
question, and the first one this line has been able to ask.
