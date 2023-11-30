@echo off
echo -------- Except for the . and @echo lines, this whole requirements-checking script is both a Windows batch script and a Unix sh script. So... enjoy.
. .venv/bin/activate
echo -------- Pipreqs seems to understate which packages are required. Which is ironic, considering that the whole thing I wanted to use it for was removing unnecessary packages, which it now provides only weak evidence about...
pip install --quiet pipreqs
pipreqs --use-local  --encoding utf-8 --print
echo -------- Let's also try deptry, ignoring the one deptry rule forbidding transitive deps.
pip install --quiet deptry
deptry . --ignore DEP003