uv --version || pip install uv --disable-pip-version-check
uv pip sync requirements.txt
streamlit run streamlit_app.py
