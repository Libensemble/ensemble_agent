import os
import sys

import numpy as np
from simf import run_six_hump_camel

from libensemble import Ensemble
from libensemble.alloc_funcs.persistent_aposmm_alloc import persistent_aposmm_alloc as alloc_f
from libensemble.executors import MPIExecutor
from libensemble.gen_funcs.persistent_aposmm import aposmm as gen_f
from libensemble.specs import AllocSpecs, ExitCriteria, GenSpecs, LibeSpecs, SimSpecs

if __name__ == "__main__":
    exctr = MPIExecutor()

    sim_app = "/home/shudson/test_mcp/script-creator/agentic/tests/six_hump_camel/six_hump_camel.x"

    if not os.path.isfile(sim_app):
        sys.exit(f"Application not found: {sim_app}")

    exctr.register_app(full_path=sim_app, app_name="six_hump_camel")

    num_workers = 4

    input_file = "/home/shudson/test_mcp/script-creator/agentic/tests/six_hump_camel/input.txt"


    libE_specs = LibeSpecs(
        nworkers=num_workers,
        gen_on_manager=True,
        sim_dirs_make=True,
        sim_dir_copy_files=[input_file],
    )

    sim_specs = SimSpecs(
        sim_f=run_six_hump_camel,
        inputs=["x"],
        outputs=[("f", float)],
        user={"input_filename": "input.txt", "input_names": ["X0", "X1"]},
    )

    n = 2
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
            "lb": np.array([0, -1]),
            "ub": np.array([1, 2])
        }
    )

    alloc_specs = AllocSpecs(
        alloc_f=alloc_f,
        
    )

    exit_criteria = ExitCriteria(sim_max=100)

    ensemble = Ensemble(
        libE_specs=libE_specs,
        gen_specs=gen_specs,
        sim_specs=sim_specs,
        alloc_specs=alloc_specs,
        exit_criteria=exit_criteria,
        executor=exctr
    )

    ensemble.add_random_streams()
    H, persis_info, flag = ensemble.run()

    if ensemble.is_manager:
        print("First 3:", H[["sim_id", "x", "f"]][:3])
        print("Last 3:", H[["sim_id", "x", "f"]][-3:])
        ensemble.save_output(__file__)
