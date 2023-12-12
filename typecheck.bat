@echo off
.venv/scripts/activate
echo:
mypy --install-types --non-interactive
echo:
echo Mypy typechecking, ignoring missing imports (I have no idea why so many of our imports are missing types, but I'm not going to spend time fixing that, so we use --ignore-missing-imports and use --no-warn-return-any (as many of our functions return something imported, and thus appear to return Any, which is disallowed in strict mode)):
echo:
mypy streamlit_app.py  --strict --ignore-missing-imports --no-warn-return-any --pretty
