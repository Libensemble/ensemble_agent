import sys
import time

import numpy as np

def six_hump_camel(H, persis_info, sim_specs, libE_info):
    """
    Evaluates the six hump camel function for a collection of points given in ``H["x"]``.
    Additionally evaluates the gradient if ``"grad"`` is a field in
    ``sim_specs["out"]``.
    """

    batch = len(H["x"])
    H_o = np.zeros(batch, dtype=sim_specs["out"])

    for i, x in enumerate(H["x"]):
        H_o["f"][i] = six_hump_camel_func(x)

        if "grad" in H_o.dtype.names:
            H_o["grad"][i] = six_hump_camel_grad(x)

    return H_o, persis_info


def six_hump_camel_func(x):
    """
    Definition of the six-hump camel
    """
    x1 = x[0]
    x2 = x[1]
    term1 = (4 - 2.1 * x1**2 + (x1**4) / 3) * x1**2
    term2 = x1 * x2
    term3 = (-4 + 4 * x2**2) * x2**2

    return term1 + term2 + term3


def six_hump_camel_grad(x):
    """
    Definition of the six-hump camel gradient
    """

    x1 = x[0]
    x2 = x[1]
    grad = np.zeros(2)

    grad[0] = 2.0 * (x1**5 - 4.2 * x1**3 + 4.0 * x1 + 0.5 * x2)
    grad[1] = x1 + 16 * x2**3 - 8 * x2

    return grad
