FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir requests

COPY config.py systems.py generator.py file_writer.py commiter.py main.py ./

RUN git config --global user.email "study@system.design" && \
    git config --global user.name "System Design"

VOLUME ["/app/questions"]

ENTRYPOINT ["python", "main.py"]
