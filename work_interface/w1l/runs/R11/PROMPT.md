This is W1-L run R11.

Your run directory is:
C:\Users\pertt\learning-lab\work_interface\w1l\runs\R11

First read:
C:\Users\pertt\learning-lab\work_interface\w1l\runs\R11\SKILL.md

That file IS the `define-lab-process` skill; you do not need to call `load_skill`. Follow
that skill for this entire run.

The frozen business-data fixtures are at these absolute paths (read them directly):
- C:\Users\pertt\learning-lab\work_interface\w1a\fixtures\supplier-statement.txt
- C:\Users\pertt\learning-lab\work_interface\w1a\fixtures\ledger-book.txt

If your file reader returns empty or errors on these files, use either of these Windows-safe
read commands (substitute the other fixture path as needed):
  powershell -Command "Get-Content -Raw 'C:\Users\pertt\learning-lab\work_interface\w1a\fixtures\supplier-statement.txt'"
  type "C:\Users\pertt\learning-lab\work_interface\w1a\fixtures\supplier-statement.txt"

Discuss the process with me and ask only the business questions required by the skill.

When the definition is complete, write exactly one artifact to:
C:\Users\pertt\learning-lab\work_interface\w1l\runs\R11\work_definition.json

Do not inspect Learning Lab validators (`work_interface\work_definition.py`), corrected/oracle
examples (`work_interface\cases\`), the W0B corrected example, previous W1 outputs
(`work_interface\w1a\runs\`, `work_interface\w1a2\`, `work_interface\w1a3\`,
`work_interface\w1a4\`, `work_interface\w1a5\`, `work_interface\w1b\`,
`work_interface\w1c\`, `work_interface\w1d\`, `work_interface\w1d2\`,
`work_interface\w1e\`, `work_interface\w1f\`, `work_interface\w1g\`, `work_interface\w1h\`, `work_interface\w1i\`, `work_interface\w1j\`, `work_interface\w1k\`), any W1 grader or
fidelity results (`RESULTS.*`, `FIDELITY.*`), closure, postmortem, analysis or disposition
notes (`CLOSURE.md`, `POSTMORTEM.md`, `F1_ANALYSIS.md`, `H_ANALYSIS.md`,
`W1A_DISPOSITION.md`), the phrasing census (`work_interface\census\`), the fidelity slice
(`work_interface\fidelity\`), the authority surface (`work_interface\authority\`), the frozen
human-answer script (`work_interface\w1a\human_answers.md`), or the other W1-L run
directories (`R01`, `R02`, `R03`, `R04`, `R05`, `R06`, `R07`, `R08`, `R09`, `R10`, `R12`). You may inspect only: your own `SKILL.md`, the two frozen fixture
files above, and information I give you during this conversation.

Do not execute the reconciliation itself. The desired artifact is a process definition
(`work_definition.json`), not reconciliation output or matched/flagged records.

Do not modify `SKILL.md`, the fixtures, repository code, tests, the roadmap, `PRODUCT.md`, or
any existing evidence.

Stop immediately after `work_definition.json` has been written.