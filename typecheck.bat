@echo off
uv --version || pip install uv --disable-pip-version-check --break-system-packages
uv run ruff check --select F --exclude cicero_empty_template.py .
set PYRIGHT_PYTHON_FORCE_VERSION=latest
export PYRIGHT_PYTHON_FORCE_VERSION=latest # One of these two lines will work, depending on your operating system...
uv run -- pyright --version || echo "Detected that pyright isn't installed. This implies the rest of the venv likely isn't ready yet either. Run the run.bat, which will install everything, and then try this again." && exit
uv run pyright
echo "-------- Mypy, non-interactively installing types..."
uv run mypy --install-types --non-interactive
echo "-------- Mypy --strict typechecking, ignoring missing imports (I have no idea why so many of our imports are missing types, but I am not going to spend time fixing that, so we use --ignore-missing-imports):"
uv run mypy cicero.py --strict --ignore-missing-imports --pretty --enable-incomplete-feature=NewGenericSyntax
uv run python -c "input('Press enter to exit...')"
