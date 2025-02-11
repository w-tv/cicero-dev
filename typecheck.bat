@echo off
uv --version || pip install uv --disable-pip-version-check --break-system-packages
echo ---------- IN THE NORMAL OPERATION OF THIS SCRIPT, SOME HARMLESS ERRORS MAY OCCUR HERE (and, perhaps, at the very beginning of the script)
alias REM=#
alias pause='uv run python -c "input(\"Press enter to exit...\")"'
REM One of these next two lines will work, depending on your operating system...
set PYRIGHT_PYTHON_FORCE_VERSION=latest
export PYRIGHT_PYTHON_FORCE_VERSION=latest
REM We have to do these, or the stub library doesn't work in mypy, as it is overridden by the type signatures of the project itself I guess. (Later versions of the official library may have all of the types we need, in which case this logic will be removed from here. google-auth-library-python-BUG-WORKAROUND (in the sense that they don't provide types, but have a py.typed); after https://github.com/googleapis/google-auth-library-python/pull/1588 is merged, we can remove the google-auth-stubs dep and just use the regular dep (see also: requirements.txt)):
python -c "from os import remove as r; r('.venv/Lib/site-packages/google/oauth2/py.typed')"
REM Can't do both in the same command because the first one might exit with an exception but the second one might still need to be done.
python -c "from os import remove as r; r('.venv/Lib/site-packages/google/auth/py.typed')"
echo ---------- END OF HARMLESS ERRORS
echo .
echo ---- RUFF:
uv run ruff check --no-cache --select F --exclude cicero_empty_template.py .
echo ---- PYRIGHT:
uv run -- pyright --version || echo "Detected that pyright isn't installed. This implies the rest of the venv likely isn't ready yet either. Run the run.bat, which will install everything, and then try this again." && pause && exit /B 2
REM /B is a cmd-ism, but bash's exit will harmlessly ignore it probably.
uv run pyright
echo ---- MYPY:
uv run mypy --install-types --non-interactive
uv run mypy . --strict --ignore-missing-imports --pretty --warn-unreachable
echo ---- PYTYPE:
uv run pytype cicero.py
REM This should be `pytype .`; alas, pytype does not support a feature of our full codebase https://github.com/google/pytype/issues/1775 PYTYPE-BUG-WORKAROUND
echo ---- SORT BY:
echo SORT BY has betrayed me once before, which is enough. Use ORDER BY instead, if there are any results below:
git grep -i "sort by" ":(exclude)typecheck.bat"
echo ---- fin
pause
