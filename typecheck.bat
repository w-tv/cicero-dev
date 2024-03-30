@echo off
uv --version || pip install uv --disable-pip-version-check
uv pip install mypy
echo -------- Mypy, non-interactively installing types...
mypy --install-types --non-interactive
echo -------- Mypy typechecking, ignoring missing imports (I have no idea why so many of our imports are missing types, but I am not going to spend time fixing that, so we use --ignore-missing-imports):
mypy cicero.py --strict --ignore-missing-imports --pretty
