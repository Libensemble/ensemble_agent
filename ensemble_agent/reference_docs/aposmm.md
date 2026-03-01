# APOSMM — Asynchronously Parallel Optimization Solver for Multiple Minima

APOSMM coordinates concurrent local optimization runs to find multiple local minima on parallel hardware. Use when the user wants to find minima, optimize, or explore an optimization landscape.

Module: `persistent_aposmm`
Function: `aposmm`
Allocator: `persistent_aposmm_alloc` (NOT the default `start_only_persistent`)
Requirements: mpmath, SciPy (plus optional packages for specific local optimizers)

## APOSMM gen_specs in generated scripts

When the MCP tool generates APOSMM scripts, run_libe.py gets this gen_specs structure:

```python
gen_specs = GenSpecs(
    gen_f=gen_f,
    inputs=[],
    persis_in=["sim_id", "x", "x_on_cube", "f"],
    outputs=[("x", float, n), ("x_on_cube", float, n), ("sim_id", int),
             ("local_min", bool), ("local_pt", bool)],
    user={
        "initial_sample_size": num_workers,
        "localopt_method": "scipy_Nelder-Mead",
        "opt_return_codes": [0],
        "nu": 1e-8,
        "mu": 1e-8,
        "dist_to_bound_multiple": 0.01,
        "max_active_runs": 6,
        "lb": np.array([...]),  # MUST match user's requested bounds
        "ub": np.array([...]),  # MUST match user's requested bounds
    }
)
```

With allocator:
```python
from libensemble.alloc_funcs.persistent_aposmm_alloc import persistent_aposmm_alloc as alloc_f
```

## Required gen_specs["user"] Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `lb` | n floats | Lower bounds on search domain |
| `ub` | n floats | Upper bounds on search domain |
| `localopt_method` | str | Local optimizer (see table below) |
| `initial_sample_size` | int | Uniform samples before starting local runs |

When using a SciPy method, must also supply `opt_return_codes` — e.g. [0] for Nelder-Mead/BFGS, [1] for COBYLA.

## Optional gen_specs["user"] Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `max_active_runs` | int | Max concurrent local optimization runs |
| `dist_to_bound_multiple` | float (0,1] | Fraction of distance to boundary for initial step size |
| `mu` | float | Min distance from boundary for starting points |
| `nu` | float | Min distance from identified minima for starting points |
| `stop_after_k_minima` | int | Stop after this many local minima found |
| `stop_after_k_runs` | int | Stop after this many runs ended |
| `sample_points` | numpy array | Specific points to sample (original domain) |
| `lhs_divisions` | int | Latin hypercube partitions (0 or 1 = uniform) |
| `rk_const` | float | Multiplier for r_k value |

## Worker Configuration

APOSMM uses one persistent generator worker. With `nworkers = 4`, there are 3 simulation workers + 1 generator.

## Local Optimizer Methods

### SciPy (no extra install)

| Method | Gradient? | `opt_return_codes` |
|--------|-----------|-------------------|
| `scipy_Nelder-Mead` | No | [0] |
| `scipy_COBYLA` | No | [1] |
| `scipy_BFGS` | Yes | [0] |

### NLopt (requires `pip install nlopt`)

| Method | Gradient? | Description |
|--------|-----------|-------------|
| `LN_SBPLX` | No | Subplex. Good for noisy/nonsmooth |
| `LN_BOBYQA` | No | Quadratic model. Good for smooth problems |
| `LN_COBYLA` | No | Constrained optimization |
| `LN_NEWUOA` | No | Unconstrained quadratic model |
| `LN_NELDERMEAD` | No | Classic simplex |
| `LD_MMA` | Yes | Method of Moving Asymptotes |

### PETSc/TAO (requires `pip install petsc4py`)

| Method | Needs | Description |
|--------|-------|-------------|
| `pounders` | fvec | Least-squares trust-region |
| `blmvm` | grad | Bounded limited-memory variable metric |
| `nm` | f only | Nelder-Mead variant |

### DFO-LS (requires `pip install dfols`)

| Method | Needs | Description |
|--------|-------|-------------|
| `dfols` | fvec | Derivative-free least-squares |

## Choosing a Local Optimizer

- **Default / simple**: `scipy_Nelder-Mead` — no extra packages
- **Smooth, bounded**: `LN_BOBYQA` (NLopt)
- **Noisy objectives**: `LN_SBPLX` (NLopt) or `scipy_Nelder-Mead`
- **Gradient available**: `scipy_BFGS` or `LD_MMA`
- **Least-squares (vector output)**: `pounders` (PETSc) or `dfols`
- **Constrained**: `scipy_COBYLA` or `LN_COBYLA`

## Important

Always use the bounds, sim_max, and paths from the user's request. Never substitute values from examples or known problem domains.
