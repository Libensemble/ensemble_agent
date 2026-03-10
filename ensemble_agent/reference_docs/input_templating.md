# Input File Templating
Detecting, creating, and validating Jinja2 templates for simulation input files.

## Overview

Simulation input files can be provided in two forms:

1. **Already templated** — contains Jinja2 markers like `{{ x0 }}`, `{{ x1 }}`
2. **Example file** — contains actual numeric values (e.g., from a previous run)

If the file is already templated, use it as-is. If it's an example file, create a templated version.

## Detecting template vs example

- If the file contains `{{` and `}}`, it's already a Jinja2 template.
- Otherwise, it's an example file that needs templating.

## Where variable names come from

In libEnsemble, the individual variable names are in `sim_specs.user["input_names"]`:
```python
sim_specs = SimSpecs(
    sim_f=run_six_hump_camel,
    inputs=["x"],           # "x" is the array name in H, NOT the template names
    outputs=[("f", float)],
    user={"input_filename": "input.txt", "input_names": ["X0", "X1"]},
)
```
Here `input_names` gives the template variable names (`X0`, `X1`). The `inputs=["x"]` is just the H array field — not what goes in the template.

For VOCS, use the variable names from the VOCS definition.

## Creating a template from an example

1. Get the variable names from the script (see above).
2. Read the example input file using `read_file` with the absolute path.
3. Identify which values correspond to the variables (typically numeric values on their own lines or in key-value pairs).
4. Replace those values with Jinja2 template markers: `{{ X0 }}`, `{{ X1 }}`, etc.
5. Save the templated file to the working directory using `write_file`.
6. Update the scripts to reference the local templated copy.

## Checking consistency

Always verify that template markers in the input file match `input_names` exactly — including case. For example, if `input_names` is `["X0", "X1"]`, the template must use `{{ X0 }}` and `{{ X1 }}`, not `{{ x0 }}`. A case mismatch will produce empty values and wrong results.

## Example

Original `input.txt`:
```
param_a = 3.14
param_b = -0.7
param_c = 2.0
mode = fast
```

Templated version (if `input_names` is `["A", "B", "C"]`):
```
param_a = {{ A }}
param_b = {{ B }}
param_c = {{ C }}
mode = fast
```

Only the numeric values for the named variables are replaced. Everything else — key names, formatting, other lines — stays exactly as-is.

## Notes

- NEVER modify the user's original input file. Always create a copy in the working directory.
- Preserve the file format exactly — only replace the variable values, keep everything else.
- Update the scripts to reference the local copy instead of the original path.
