# Finding Objective Fields

## libEnsemble scripts

The objective field name is defined in `sim_specs` outputs in the run script (e.g. `run_libe.py`).

Look for:
```python
sim_specs = SimSpecs(
    ...
    outputs=[("f", float)],  # "f" is the objective field name
)
```

The field name in `outputs` (e.g. `"f"`) matches the field name in the `.npy` results file.

## Common patterns
- Single objective: `outputs=[("f", float)]`
- Multiple outputs: `outputs=[("f", float), ("grad", float, 2)]` — `"f"` is typically the objective
- The objective is the scalar float output used by the generator for optimization
