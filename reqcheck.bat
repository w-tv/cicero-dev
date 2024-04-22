@echo off
echo -------- This whole requirements-checking script is both a Windows batch script and a Unix sh script. So... enjoy.
uv --version || pip install uv --disable-pip-version-check --break-system-packages
uv pip install pipreqs deptry
echo -------- Pipreqs seems to understate which packages are required. Which is ironic, considering that the whole thing I wanted to use it for was removing unnecessary packages, which it now provides only weak evidence about...
uv run pipreqs --use-local --print --ignore .venv
echo -------- Let us also try deptry, ignoring the one deptry rule forbidding transitive deps. This also seems to underestimate sometimes.
uv run deptry . --ignore DEP003
uv run python -c "input('Press enter to exit...')"
