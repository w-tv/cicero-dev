uv --version || pip install --disable-pip-version-check --break-system-packages uv
uv pip install -r requirements.txt || uv venv && uv pip install -r requirements.txt
uv run streamlit run -- cicero.py --disable_user_authentication_requirement_DO_NOT_USE_THIS_FLAG_WITH_PUBLIC_INSTANCES_OF_CICERO_ITS_ONLY_FOR_LOCAL_TESTING_USE
uv run python -c "input('Press enter to exit...')"
