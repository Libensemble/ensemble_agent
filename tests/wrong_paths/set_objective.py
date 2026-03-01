import numpy as np


def set_objective_value():
    try:
        data = applenp.loadtxt("output.txt", ndmin=1)
        return data[-1]
    except Exception:
        return np.nan
