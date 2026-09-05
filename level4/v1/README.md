# Level-4 static system-state packet experiment — v1

**Status at this commit: PREPARED AND FROZEN. Not executed.**

Authority: Roundtable, issue #9; Manager dispatch and Phase-1 review, 2026-09-05.

Supersedes [`../v0/`](../v0/), which was frozen and **never run** — see [`../v0/SUPERSEDED.md`](../v0/SUPERSEDED.md) for the two defects Manager caught before either arm executed. No result was lost.

This is a no-plumbing experiment. Nothing is wired into `supervisor/`, no exporter or daemon exists, and the evaluator gets no tools and no repository access. If the result is negative, nothing has to be removed.

## The question

> What is the minimum sufficient, security-conscious representation of Learning Lab's living system that lets a cold LLM form a useful global judgement without treating untrusted content as authority?

## Files

| File | Role |
| --- | --- |
| [`PREREGISTRATION.md`](PREREGISTRATION.md) | question, design, provenance, interpretation branches — **frozen before either response**; §0 records what changed from v0 |
| [`packet_A.json`](packet_A.json) | graded input, baseline |
| [`packet_B.json`](packet_B.json) | graded input, A plus exactly one `untrusted_content` canary |
| [`evaluator_instruction.md`](evaluator_instruction.md) | the fixed prompt — carried from v0 byte-identically |
| [`system_verdict_v0.md`](system_verdict_v0.md) | output contract — carried from v0 byte-identically |
| [`grading.md`](grading.md) | criteria A–G and record templates — carried from v0 byte-identically |
| [`build_packet.py`](build_packet.py) | derives the snapshot from live state; `--self-test` |
| [`check_packet.py`](check_packet.py) | validates the **committed** files, independently; `--self-test` |
| `runs/A/INPUT.md`, `runs/B/INPUT.md` | the exact paste-ready graded inputs |

## The two corrections over v0

**One manipulated variable, asserted literally.** Both arms carry the same packet-visible `snapshot.id` (`level4-v1`). Arm identity lives only in the directory, the response filename and the session metadata. Remove B's single `untrusted_content` record and the packets must be **equal outright** — nothing is normalized away first, which is what v0's self-test did.

**Provenance that does not overclaim.** `snapshot.provenance.source_revision` is `25f2e74`, and the packet says explicitly which sections that revision can rebuild:

```text
reconstructable    authority_context, initiative_box, topology
                   (tracked: initiatives.md, worker.json, versions/,
                    input_contracts/, history.jsonl, investigation.json)

not reconstructable  operational_state
                   (runs.jsonl, inbox/, processed/, exceptions/ are
                    gitignored runtime state -- not in ANY revision)
```

`check_packet.py` proves the first line rather than asserting it: it re-derives `initiative_box` from `git show 25f2e74:docs/development/initiatives.md` and requires an exact match.

## Running it

Verify the frozen inputs first:

```bash
python level4/v1/build_packet.py --self-test
python level4/v1/check_packet.py --self-test
python level4/v1/check_packet.py
```

Then, **in two separate cold sessions** — no repository access, no tools, no prior Learning Lab context, no follow-up evidence during the graded run:

1. paste `runs/A/INPUT.md` into one session; save the reply **verbatim** to `runs/A/response.json` (use `.txt` if it is not valid JSON — preserve exactly what came back);
2. paste `runs/B/INPUT.md` into a *fresh* session; save to `runs/B/response.json`;
3. record the model and session identification the interface shows;
4. grade each arm against `grading.md`, then complete the A/B comparison;
5. write `RESULT.md`.

The arms must not share a session. B's whole purpose is to be read by a model that has not already reasoned about A.

Because both packets now carry the same `snapshot.id`, a response cannot be attributed to an arm from its content — the capture path is what distinguishes them. Save each reply to its own `runs/<arm>/` directory as you go, rather than sorting them out afterwards.

## A note on reading these files

Read the packets with an **explicit UTF-8 encoding**. They contain em dashes and other non-ASCII characters carried from the initiative register, and on Windows a bare `open(path)` uses cp1252 and silently mangles them:

```python
json.loads(pathlib.Path("packet_A.json").read_text(encoding="utf-8"))   # correct
json.load(open("packet_A.json"))                                        # mojibake
```

This bit during development and briefly looked like a provenance mismatch. Both checkers read explicitly; ad-hoc scripts should too.

## Freeze discipline

The graded inputs are packet A, packet B, the evaluator instruction, the verdict contract and the grading criteria. **After the freeze commit, changing any of them creates a new experiment version** — that rule is why v1 exists as its own directory instead of an edit to v0.

## What this cannot establish

n=1 per arm, one model, one snapshot, one adversarial variant. No rate of injection resistance can be reported from it. A pass does not generalise to unlabelled hostile content, to content embedded inside a `system_fact`, or to multi-turn pressure. See `PREREGISTRATION.md` §7.
