import sys
from IPython.core.interactiveshell import InteractiveShell
from IPython import start_ipython
import runpy


def run_module(self, mod_name, where):
    where.update(
        runpy.run_module(
            str(mod_name), run_name="__main__",
            alter_sys=True
        )
    )


InteractiveShell.safe_run_module = run_module

result = start_ipython(['-m', 'pytest', '--'] + sys.argv[1:])
