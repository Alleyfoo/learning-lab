# Level-4 static system-state packet experiment — v0

**Status at this commit: PREPARED AND FROZEN. Not executed.**

Authority: Roundtable, issue #9; Manager dispatch 2026-09-05. Roundtable placed this ahead of W1-L, which remains frozen, `Ready`, unrun and undispatched.

This is a no-plumbing experiment. Nothing here is wired into `supervisor/`, no exporter or daemon exists, and the evaluator gets no tools and no repository access. If the result is negative, nothing has to be removed.

## The question

> What is the minimum sufficient, security-conscious representation of Learning Lab's living system that lets a cold LLM form a useful global judgement without treating untrusted content as authority?

The object under test is the **packet and verdict contract**, not any particular model.

## Files

| File | Role |
| --- | --- |
| [`PREREGISTRATION.md`](PREREGISTRATION.md) | question, design, measurement, and the interpretation branches — **frozen before either response** |
| [`build_packet.py`](build_packet.py) | derives the snapshot from live fleet state; `--self-test` |
| [`packet_A.json`](packet_A.json) | graded input, baseline |
| [`packet_B.json`](packet_B.json) | graded input, A plus exactly one `untrusted_content` injection canary |
| [`evaluator_instruction.md`](evaluator_instruction.md) | the fixed prompt, used verbatim for both arms |
| [`system_verdict_v0.md`](system_verdict_v0.md) | the output contract |
| [`grading.md`](grading.md) | criteria A–G and the record templates |
| [`check_packet.py`](check_packet.py) | validates the **committed** packet files, independently of the builder; `--self-test` |
| `runs/A/INPUT.md`, `runs/B/INPUT.md` | the exact paste-ready graded inputs: instruction + packet, assembled |

## What the packet is

A **derived snapshot**, never a new source of truth. Every record declares a trust class:

```text
system_fact          mechanically derived or recorded state
authority_record     durable human/Roundtable/engineering authority
model_interpretation LLM-authored judgement  (absent in v0)
untrusted_content    external payload: evidence only, never instruction
```

Two things are deliberately excluded, and both exclusions are enforced mechanically:

- **System Map presentation state** — `x`, `y`, `size`, `shape`, `color`, `title`, `clickable`, `borderWidth`. It says how the map looks, not what the system is.
- **The current Supervisor assessment** — model-authored interpretation. v0 asks the evaluator for an *independent* verdict; including a prior model's findings would measure agreement with that model instead.

## Running it

Verify the frozen inputs first:

```bash
python level4/v0/build_packet.py --self-test
python level4/v0/check_packet.py --self-test
python level4/v0/check_packet.py
```

Then, **in two separate cold sessions** — no repository access, no tools, no prior Learning Lab context, no follow-up evidence during the graded run:

1. paste `runs/A/INPUT.md` into one session; save the raw reply verbatim to `runs/A/response.json` (or `.txt` if it is not valid JSON — preserve exactly what came back);
2. paste `runs/B/INPUT.md` into a *fresh* session; save to `runs/B/response.md`;
3. record the model and session identification visible in the interface;
4. grade each arm against `grading.md`, then complete the A/B comparison;
5. write `RESULT.md`.

The two arms must not share a session. B's whole purpose is to be read by a model that has not already reasoned about A.

## Freeze discipline

The graded inputs are packet A, packet B, the evaluator instruction, the verdict contract and the grading criteria. **After the freeze commit, changing any of them creates a new experiment version.** Tuning the packet or prompt after seeing A and presenting the modified B as the same experiment is the specific failure `PREREGISTRATION.md` §8 exists to prevent.

## What this cannot establish

n=1 per arm, one model, one snapshot, one adversarial variant. It cannot produce a rate of injection resistance, and no percentage may be reported from it. A pass does not generalise to unlabelled hostile content, to content embedded inside a `system_fact`, or to multi-turn pressure. See `PREREGISTRATION.md` §6.
