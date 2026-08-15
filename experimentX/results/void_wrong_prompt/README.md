# VOID — these captures are not Experiment X

A harness bug, not a result. `run_X.py` did:

```python
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LAB / "experimentW" / "harness"))
```

The second insert put W's harness ahead of X's, so `import build_prompts`
resolved to **W's** module. Stage 2 therefore asked the model to build the
calendar reservation node, which is why every block names `holidays` and
`reservations` — collections that do not exist in X's fixtures.

The model never saw X's stage-2 prompt. Preserved as non-evidential, the same
call made for the corrupted `ollama run` captures in an earlier experiment.
Nothing here is graded and nothing here bears on X's outcome.
