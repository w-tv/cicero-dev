# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.11-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Turns off the cache dir for pip, which is useless for a docker image and only takes up space.
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" app && chown -R app /app

# # Install pip requirements
# COPY requirements.txt .
# RUN python -m pip install --no-cache-dir -r requirements.txt
RUN uv --version || pip install uv --disable-pip-version-check --break-system-packages
RUN uv pip install -r requirements.txt || uv venv && uv pip install -r requirements.txt


USER app
EXPOSE 8501
# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
#CMD ["python", "cicero.py"]
#CMD ["streamlit", "run", "cicero.py", "--server.port=8501", "--server.address=0.0.0.0"]
CMD uv run streamlit run cicero.py
