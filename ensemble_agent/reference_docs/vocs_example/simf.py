import numpy as np
import jinja2
from libensemble.message_numbers import TASK_FAILED, WORKER_DONE


def set_objective_value():
    try:
        data = np.loadtxt("output.txt", ndmin=1)
        return data[-1]
    except Exception:
        return np.nan


def set_input_file_params(H, sim_specs, ints=False):
    """
    Parameterize an input file using VOCS variable names from H.

    Each variable is a scalar field in H
    (e.g., H["x0"], H["x1"]).
    The input_names in sim_specs["user"] should match both the
    VOCS variable names and the template placeholders.
    """
    input_file = sim_specs["user"].get("input_filename")
    input_names = sim_specs["user"].get("input_names")
    if not input_file or not input_names:
        return
    input_values = {}
    for name in input_names:
        value = int(H[name][0]) if ints else H[name][0]
        input_values[name] = value
    with open(input_file, "r") as f:
        template = jinja2.Template(f.read())
    with open(input_file, "w") as f:
        f.write(template.render(input_values))


def run_sim(H, persis_info, sim_specs, libE_info):
    """Runs an MPI application, reading input from a templated file."""

    calc_status = 0

    set_input_file_params(H, sim_specs)

    exctr = libE_info["executor"]

    task = exctr.submit(
        app_name=sim_specs["user"]["app_name"],
    )

    task.wait()

    f = set_objective_value()

    if np.isnan(f):
        calc_status = TASK_FAILED
    else:
        calc_status = WORKER_DONE

    outspecs = sim_specs["out"]
    output = np.zeros(1, dtype=outspecs)
    output["f"][0] = f

    return output, persis_info, calc_status
