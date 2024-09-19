@echo off
uv --version || pip install uv --disable-pip-version-check --break-system-packages
uv run ruff check --select F --exclude cicero_empty_template.py .
echo ---------- IN THE NORMAL OPERATION OF THIS SCRIPT, SOME HARMLESS ERRORS WILL OCCUR HERE
set PYRIGHT_PYTHON_FORCE_VERSION=latest
export PYRIGHT_PYTHON_FORCE_VERSION=latest # One of these two lines will work, depending on your operating system...
python -c "from os import remove as r; r('.venv/Lib/site-packages/google/oauth2/py.typed') #We have to do these, or the stub library doesn't work in mypy, as it is overridden by the type signatures of the project itself I guess. (Later versions of the official library may have all of the types we need, in which case this logic will be removed from here. google-auth-library-python-BUG-WORKAROUND (in the sense that they don't provide types, but have a py.typed); after https://github.com/googleapis/google-auth-library-python/pull/1588 is merged, we can remove the google-auth-stubs dep and just use the regular dep (see also: requirements.txt))"
python -c "from os import remove as r; r('.venv/Lib/site-packages/google/auth/py.typed') #Can't do both in the same command because the first one might exit with an exception but the second one might still need to be done."
echo ---------- END OF HARMLESS ERRORS
uv run -- pyright --version || echo "Detected that pyright isn't installed. This implies the rest of the venv likely isn't ready yet either. Run the run.bat, which will install everything, and then try this again." && exit
uv run pyright
echo "-------- Mypy, non-interactively installing types..."
uv run mypy --install-types --non-interactive
echo "-------- Mypy --strict typechecking, ignoring missing imports (I have no idea why so many of our imports are missing types, but I am not going to spend time fixing that, so we use --ignore-missing-imports):"
uv run mypy cicero.py --strict --ignore-missing-imports --pretty --enable-incomplete-feature=NewGenericSyntax #mypy-BUG-WORKAROUND: I expect the --enable-incomplete-feature=NewGenericSyntax flag to be unneeded in mypy 1.12 and beyond. Unfortunately, as of 2024-09-19 we only have 1.11.2
uv run python -c "input('Press enter to exit...')"
