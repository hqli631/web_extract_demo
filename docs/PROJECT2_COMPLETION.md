# Project 2 completion record

## Delivered loop

`project2_agent.py` now provides one reproducible entry point for:

1. loading a hashed task with generation, development and final holdout roles;
2. obtaining a candidate from a pluggable `mock` or DashScope-compatible Qwen provider;
3. checking and executing the candidate with the existing AST and timeout boundary;
4. converting execution/quality findings into feedback;
5. repairing at most `--max-rounds` times; and
6. running the holdout only after the candidate is frozen, without feeding its result back.

The trace stores candidate hashes, page roles and hashes, per-round outputs, feedback, holdout status, API-call count and returned usage. `DASHSCOPE_API_KEY` is read only from the process environment.

## Reproduce the offline demonstration

```powershell
Set-Location 'D:/codex project/web_extract_demo'
& './.venv/Scripts/python.exe' -E -X utf8 './project2_agent.py' `
  --provider mock --max-rounds 1 --output output/project2/final
```

Expected evidence is two mock rounds, zero API calls, a passing final holdout contract check and `output/project2/final/trace.json`. This proves the control flow only; it is not a Qwen quality result.

## Fresh evaluation material

`data/project2/python_blog/manifest.json` records five newly retrieved Python Insider pages: two generation pages, one development page and two final holdouts. Their URLs and SHA-256 values are frozen. Fresh retrieval means they were not used in this local debugging session; it does not prove that a model has never seen the site during pretraining. The current Sina mock candidate is not claimed to solve the Python Insider layout.

## Honest boundary

The repository does not claim a live Qwen run unless a user supplies a key and executes `--provider dashscope`. The Windows AST check plus temporary subprocess is a defensive capability boundary, not an operating-system sandbox for hostile code. For untrusted live candidates use the Linux `bubblewrap + prlimit` path before production-style execution. Contract pass is not semantic completeness or purity accuracy.
