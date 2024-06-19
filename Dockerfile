# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.12.3-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1


WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" app && chown -R app /app && apt update && apt install git gcc -y && apt clean

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

USER app
EXPOSE 8501
# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
#CMD ["python", "cicero.py"]
CMD ["streamlit", "run", "cicero.py", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false", "--server.headless=true"] #The --server.headless=true bit is probably redundant (I think in our deployment it defaults to true anyway, based on https://docs.streamlit.io/develop/api-reference/configuration/config.toml#server) but I'm doing it just in case this prevents 'Bad message format: Tried to use SessionInfo before it was initialized' errors we keep getting (probably unrelated).
