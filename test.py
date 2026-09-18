# check_env.py
import sys, platform
import fmpy

print("Python version :", sys.version)
print("Architecture   :", platform.architecture())
print("fmpy version   :", fmpy.__version__)