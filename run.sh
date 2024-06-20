echo "if you dont use wsl, try (renaming the file extension, then) running run.sh directly as a bat script, it will work."
uv --version || pip install --disable-pip-version-check --break-system-packages uv
uv pip install -r requirements.txt || uv venv && uv pip install -r requirements.txt
uv run streamlit run cicero.py
uv run python -c "input('Press enter to exit...')"
