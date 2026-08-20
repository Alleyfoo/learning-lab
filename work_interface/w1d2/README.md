# W1-D2 — Surface B only, re-prepared after the W1-D harness void

W1-D was closed `HARNESS-VOID` (`../w1d/CLOSURE.md`): all three runs died on turn
1 with `blocks_delivered = 0`, because the forbidden-path detector held bare
lexical markers and scanned serialized tool payloads including file **content**.
The word `authority` appears eleven times in the authorized skill r2, so reading
its own `SKILL.md` tripped the boundary before the lifecycle began.

**W1-D2 keeps every intended W1-D experimental variable unchanged** and fixes
only the detector. Run IDs K1/K2/K3 are retired; this pack uses **L1/L2/L3**.

## Pinned, unchanged

```text
model                qwen3.5:9b, shared local Goose/Ollama config
skill                define-lab-process r2  0230969ea7fd00ed…
fixtures             supplier-statement d0cb95ab…   ledger-book 284861d7…
canonical block      46158afa4b7e682a…  693 bytes, rows 0-5, hash-checked at startup
validator            work_definition_version 0, aligned, 27 refusal codes
fidelity instrument  fidelity_check.py 11984c096b8fd74f… (gate refuses on drift)

worker capability environment -- IDENTICAL to W1-C:
  goose acp, session mode `auto`, no client filesystem capability,
  shell available exactly as before, NO permission policy, NO denials
```

**Surface A remains unenforced.** A4 remains shadow-only.

## The lifecycle under test — Surface B only

```text
initial session/prompt              -> the run prompt
first completed non-artifact turn   -> the canonical block, EXACTLY ONCE
every subsequent non-artifact turn  -> exactly "Continue."
first artifact                      -> terminate immediately
```

Post-block questions receive no business answer regardless of wording; full agent
text is recorded verbatim. Corrected silent-turn budget preserved: at most two
consecutive re-entries, only non-empty visible content resets the streak, tool
activity never does. Ownership of rows 6/7 and `output_order` unchanged.

## The harness correction

Lexical substring scanning is replaced by **structured path extraction**
(`work_interface/harness/path_guard.py`):

```text
extract candidate path(s) from PATH-BEARING FIELDS ONLY
   rawInput.path / file_path / source / destination / target / filename / file
   path-shaped TOKENS from rawInput.command / cmd / shell / script
   locations[].path
   -> canonicalize: resolve against session cwd, slash direction, "." and "..",
      case-fold on Windows
   -> compare against an explicit, PATH-SHAPED forbidden set
```

**Never scanned:** file contents, tool output, assistant messages, thought text,
TODO text, titles, or arbitrary JSON serialization. Every forbidden entry is
anchored to a real resource that must exist on disk; `verify_prep` check 15
asserts there are no bare lexical markers left.

## Regressions against the exact W1-D evidence

`harness/selftest_path_guard.py` replays the **real** tool updates recorded in
K1/K2/K3's frozen transcripts:

```text
K1 16 updates, K2 24, K3 22  -> zero violations   (the defect, proven fixed)
tool_call_update carrying SKILL.md text          -> no candidate path at all
K3's todo "## define-lab-process run k3 analysis"-> no candidate path at all
sibling run / human_answers.md / validator /
  oracle cases / prior pack run / fidelity tool  -> VIOLATION
shell naming a forbidden path                    -> VIOLATION
shell echoing the words authority, fidelity      -> no violation
".." traversal (windows, posix, mixed, dot-segs) -> VIOLATION
own SKILL.md relative, bare, and own artifact    -> allowed
upper-cased forbidden path                       -> VIOLATION
forbidden path in content/before/after/output/
  text/title/description/thought                 -> NOT a path reference
```

`verify_prep` check 15 replays the same frozen evidence inside the pack's own
gate, judged in each K run's own context.

## Runs, N, and verdicts

**L1, L2, L3. N is fixed at 3** and is not increased after seeing the outcome.

```text
STRUCTURAL   grade.py          -> RESULTS.md / RESULTS.json          (primary)
FIDELITY     fidelity_gate.py  -> FIDELITY.md / FIDELITY.json        (primary)
A4_SHADOW    a4_shadow.py      -> A4_SHADOW.md / A4_SHADOW.json      (descriptive)
```

A4 is **not** in the primary verdict. The batch runs `fs_enforcing=False`; the
audit runs only after the complete batch and cannot terminate, alter, rescue or
influence L1/L2/L3.

## Discipline

- Do not increase N after seeing the outcome.
- Do not rescue a run, alter the block, change lifecycle behaviour, or rerun an
  individual run.
- Do not repair an artifact. A bad run is the measurement.
- Do not adopt Surface A mid-experiment, and do not act on `A4_SHADOW`.
- K1/K2/K3 are defect evidence. Their structural, fidelity and A4 results are not
  worker evidence and must not be cited as such.

## Execution

```bash
python work_interface/harness/selftest_path_guard.py && python work_interface/harness/selftest_single_block.py && python work_interface/w1d2/harness/run_batch.py --run all && python work_interface/w1d2/grade.py && python work_interface/w1d2/fidelity_gate.py && python work_interface/w1d2/a4_shadow.py
```
