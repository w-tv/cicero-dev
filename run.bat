uv --version || pip install uv --disable-pip-version-check
uv pip install -r requirements.txt || uv venv && uv pip install -r requirements.txt
call .venv/Scripts/activate
.venv/Scripts/python -m streamlit run cicero.py
deactivate
