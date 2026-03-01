# Post-Generation Checklist

The CreateLibEnsembleScripts tool generates structurally correct scripts from templates. Do not change the overall structure. After generation, verify these specific values match the user's request:

In run_libe.py:
- `sim_app`: must be the user's executable path (not blank, not a placeholder)
- `lb`, `ub` in gen_specs["user"]: must match the user's requested bounds
- `sim_max` in exit_criteria: must match the user's requested simulation count
- `num_workers`: must match the user's requested worker count

In simf.py:
- The output filename in `set_objective_value()`: must match the user's output file (e.g. "output.txt")
- The `app_name` in `exctr.submit()` must match `exctr.register_app()` in run_libe.py

Fix only these values if wrong. Do not rewrite or restructure anything.
