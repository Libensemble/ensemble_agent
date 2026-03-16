import os
import sys

from gest_api.vocs import VOCS
from xopt.generators.bayesian.expected_improvement import ExpectedImprovementGenerator

from simf import run_sim

from libensemble import Ensemble
from libensemble.alloc_funcs.start_only_persistent import only_persistent_gens as alloc_f
from libensemble.executors import MPIExecutor
from libensemble.specs import AllocSpecs, ExitCriteria, GenSpecs, LibeSpecs, SimSpecs

if __name__ == "__main__":
    exctr = MPIExecutor()

    sim_app = "/path/to/six_hump_camel.x"

    if not os.path.isfile(sim_app):
        sys.exit(f"Application not found: {sim_app}")

    exctr.register_app(full_path=sim_app, app_name="six_hump_camel")

    batch_size = 4

    input_file = "/path/to/input.txt"

    libE_specs = LibeSpecs(
        nworkers=batch_size,
        gen_on_manager=True,
        sim_dirs_make=True,
        sim_dir_copy_files=[input_file],
    )

    vocs = VOCS(
        variables={"x0": [0, 3], "x1": [0, 3]},
        objectives={"f": "MINIMIZE"},
    )

    gen = ExpectedImprovementGenerator(vocs=vocs)

    gen_specs = GenSpecs(
        generator=gen,
        initial_batch_size=8,
        initial_sample_method="uniform",
        batch_size=batch_size,
        vocs=vocs,
    )

    sim_specs = SimSpecs(
        sim_f=run_sim,
        vocs=vocs,
        user={
            "input_filename": "input.txt",
            "input_names": ["x0", "x1"],
            "app_name": "six_hump_camel",
        },
    )

    alloc_specs = AllocSpecs(alloc_f=alloc_f)

    exit_criteria = ExitCriteria(sim_max=20)

    ensemble = Ensemble(
        libE_specs=libE_specs,
        gen_specs=gen_specs,
        sim_specs=sim_specs,
        alloc_specs=alloc_specs,
        exit_criteria=exit_criteria,
        executor=exctr,
    )

    H, persis_info, flag = ensemble.run()

    if ensemble.is_manager:
        print(f"Completed {len(H)} simulations")
        ensemble.save_output(__file__)
