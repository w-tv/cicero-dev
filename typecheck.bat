@echo off
uv --version || pip install uv --disable-pip-version-check --break-system-packages
uv pip install mypy
echo "-------- Mypy, non-interactively installing types..."
uv run mypy --install-types --non-interactive
echo "-------- Mypy typechecking, ignoring missing imports (I have no idea why so many of our imports are missing types, but I am not going to spend time fixing that, so we use --ignore-missing-imports):"
uv run python -c "import shutil; shutil.copytree('stubs_for_external_projects', '.venv/Lib/site-packages', dirs_exist_ok=True) #allows us to use our own stubs"
uv run python -c "import os; f = '.venv/Lib/site-packages/torch/py.typed'; os.path.isfile(f) and os.remove(f) #temporary fix for https://github.com/pytorch/pytorch/issues/124897 . It's quite possible that this code will FileNotFound after the first time it's run. Who cares?"
uv run mypy cicero.py --strict --ignore-missing-imports --pretty
uv run python -c "input('Press enter to exit...')"
