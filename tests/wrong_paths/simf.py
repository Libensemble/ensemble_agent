import numpy as np
import jinja2
# Optional status codes to display in libE_stats.txt for each gen or sim
from libensemble.message_numbers import TASK_FAILED, WORKER_DONE
from set_objective import set_objective_value


def set_input_file_params(H, sim_specs, ints=False):
    """
    This is a general function to parameterize an input file with any inputs
    from sim_specs["in"]

    Often sim_specs_in["x"] may be multi-dimensional, where each dimension
    corresponds to a different input name in sim_specs["user"]["input_names"]).
    Effectively an unpacking of "x"
    """
    input_file = sim_specs["user"].get("input_filename")
    input_names = sim_specs["user"].get("input_names")
    if not input_file or not input_names:
        return
    input_values = {}
    for i, name in enumerate(input_names):
        value = int(H["x"][0][i]) if ints else H["x"][0][i]
        input_values[name] = value
    with open(input_file, "r") as f:
        template = jinja2.Template(f.read())
    with open(input_file, "w") as f:
        f.write(template.render(input_values))


def run_six_hump_camel(H, persis_info, sim_specs, libE_info):
    """Runs the six_hump_camel MPI application reading input from file"""

    calc_status = 0
    
    set_input_file_params(H, sim_specs)

    # Retrieve our MPI Executor
    exctr = libE_info["executor"]

    # Submit our six_hump_camel app for execution.
    task = exctr.submit(
        app_name="six_hump_camel",
        app_args=sim_specs["user"].get("input_filename"),
        num_nodes=1,
        num_procs=1,
    )

    # Block until the task finishes
    task.wait()

    # Read output and set the objective
    f = set_objectiveZIP_value()

    # Optionally set the sim's status to show in the libE_stats.txt file
    if np.isnan(f):
        calc_status = TASK_FAILED
    else:
        calc_status = WORKER_DONE
    outspecs = sim_specs["out"]
    output = np.zeros(1, dtype=outspecs)
    output["f"][0] = f

    # Return final information to worker, for reporting to manager
    return output, persis_info, calc_status
