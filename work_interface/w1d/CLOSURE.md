# W1-D — closed as `HARNESS-VOID`

**No Surface B data was produced.** All three runs were killed on turn 1, with
`blocks_delivered = 0`, before the lifecycle under test began.

> **K1/K2/K3 are preserved exactly, as evidence of the harness defect.**
> Their structural, fidelity and A4 results are **not worker evidence** and must
> never be cited as such. The run IDs K1/K2/K3 are retired and are not reused.

```text
run   completion/lifecycle              structural    fidelity      A4 shadow
K1    CONTESTED turn 1, 0 blocks sent   NO_ARTIFACT   NO_ARTIFACT   CLEAN (vacuous)
K2    CONTESTED turn 1, 0 blocks sent   NO_ARTIFACT   NO_ARTIFACT   CLEAN (vacuous)
K3    CONTESTED turn 1, 0 blocks sent   NO_ARTIFACT   NO_ARTIFACT   CLEAN (vacuous)
```

Every column is vacuous for a different reason: `NO_ARTIFACT` because no run
reached an artifact; no fidelity information because there was nothing to grade;
and `A4_SHADOW = CLEAN` only because a worker killed on turn 1 had no opportunity
to create a side file — it is **not** evidence that the W1-C `temp_skill.txt`
behaviour changed.

## Root cause

```text
1  FORBIDDEN_EXTRA contained BARE LEXICAL MARKERS -- "authority", "fidelity",
   "census", "ANALYSIS" -- where W1-C had used path-shaped markers.
2  Forbidden-path detection scanned the SERIALIZED TOOL PAYLOAD, including file
   CONTENT carried on tool_call_update, rather than actual path-bearing arguments.
3  Skill r2 uses the word "authority" eleven times, including line 23:
       "the evidence/authority basis of each load-bearing decision"
   so reading the AUTHORIZED frozen SKILL.md falsely tripped the boundary, on
   turn 1, before the Surface-B lifecycle began.
```

K3 additionally tripped `ANALYSIS` by writing a todo note titled
`## define-lab-process run k3 analysis` — its own prose, in a field that is not a
path at all.

Confirmed directly in the frozen transcripts: the matching payload is the
`tool_call_update` carrying the `SKILL.md` text.

## Attribution

This is a **harness construction defect introduced in `e6714c5`**, authored when
the W1-D batch runner's forbidden list was expanded. It is not worker behaviour,
not a lifecycle result, and not attributable to `define-lab-process`.

## Correction, and where it lands

W1-D2 replaces lexical substring scanning with **structured path extraction**:
candidate paths are taken only from fields that semantically name paths, are
canonicalized against the session cwd, and are compared against an explicit,
path-shaped forbidden set. File contents, tool output, assistant messages,
thought text, TODO text, titles and arbitrary JSON serialization are never
scanned.

The exact frozen K1/K2/K3 evidence is carried into W1-D2 as regression cases, so
this defect cannot recur silently.

W1-D2 keeps every intended W1-D experimental variable unchanged and uses fresh
run IDs **L1/L2/L3**.
