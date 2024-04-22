uv --version || pip install uv --disable-pip-version-check --break-system-packages
uv pip install -r requirements.txt || uv venv && uv pip install -r requirements.txt
uv run streamlit run cicero.py
uv run python -c "input('Press enter to exit...')"
