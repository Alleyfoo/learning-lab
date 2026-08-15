# Calendar job — unattended automation

The reservation example stripped back to what it is actually for: **a job that
runs without anyone watching.** No per-run human approval, no prompt, no
confirmation. The established task definition is the authority, and the runtime
obeys it.

**No LLM anywhere at runtime**, in either implementation or anything they call.

## The two paths, and why both exist

```text
reference.py     hand-written. What a person writes in ten minutes: three ifs
                 and an append. The rules live in the control flow.
unattended.py    the modelled path. The same job as a declared definition,
                 executed by the shared reservation executor.
```

The reference is not a stepping stone to be deleted. It is the **independent
answer** the modelled path is measured against. If the two disagree, at least one
is wrong, and `equivalence.py` says so without anyone having to relitigate which
reading of the spec was intended.

## What the definition is produced from

```text
known schema        a date is requested; holidays and reservations are lists
                    of ISO dates
holiday source      fixtures/holidays.json          read-only
reservation source  fixtures/reservations.json      READ AND APPENDED TO
stated purpose      recorded in the definition itself, in `purpose`
```

`purpose` is **inert to execution**. It does not change a single decision — the
rules do. It is there because six months from now the question "what was this
job supposed to do?" has a written answer next to the rules that answer it, and
because a definition whose purpose and rules disagree is a thing a reader can
then notice.

## What "established" means, and what it does not

There is no approval in the run. There is a check on **which authority is in
force**:

```text
definition INVALID   the run stops. An unattended job with no one to ask must
                     not fall back on a best guess.
definition CHANGED   refused when a digest is pinned via `--established`. This
                     is not approval -- it is refusing to silently obey an
                     edited authority.
```

Both are demonstrated: removing the holiday rule is refused as a changed
authority, and an unknown `on_accept` is refused as invalid.

## Where the append happens

`execute()` returns the reservation list as it *would* stand and writes nothing.
Persisting is the **runtime's** act, on acceptance only. Keeping those apart is
why the same executor can be previewed harmlessly in the modeller and trusted
here.

## Equivalence, and why final state is the half that matters

Both paths run the same six requests from identical copies of the same data, and
must agree on every decision **and** on the reservation list left behind.

```text
2026-07-14   free day                    ACCEPT, appended
2026-07-14   the SAME day again          REJECT ALREADY_RESERVED -- the only
                                         case proving the append took EFFECT
2026-12-25   holiday                     REJECT HOLIDAY
2026-02-30   looks like a date, is not   REJECT INVALID_DATE
2026-03-10   already in the source       REJECT ALREADY_RESERVED
2026-08-01   another free day            ACCEPT
```

Three broken references are run as canaries, and **`append_twice` is the one
that earns the state comparison its place**:

```text
skip_holiday   decisions diverge, state diverges
never_append   decisions diverge, state diverges
append_twice   decisions AGREE, state diverges
```

An implementation that decides perfectly and writes the wrong data would pass any
check that only compared verdicts.

## Stated limitation

One request sequence of six, one holiday list, one starting state. This says the
two implementations agree **here** — it is not a proof of equivalence over all
inputs. Concurrency, retries, and a request arriving while the file is being
written are all absent, and a real unattended job would have to answer them.
