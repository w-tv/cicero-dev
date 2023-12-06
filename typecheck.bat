@echo off
.venv/scripts/activate
echo:
mypy --install-types --non-interactive
echo:
echo Mypy typechecking, ignoring missing imports (I have no idea why so many of our imports are missing types, but I'm not going to spend time fixing that):
echo:
mypy streamlit_app.py --ignore-missing-imports --pretty
