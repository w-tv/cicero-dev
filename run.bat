python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt --disable-pip-version-check --quiet
streamlit run streamlit_app.py
