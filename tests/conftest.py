import os
import sys

# The skill scripts are imported straight from the plugin tree, and some tests run them as subprocesses: keep bytecode
# out of it in both cases (an installed plugin must not ship __pycache__).
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
