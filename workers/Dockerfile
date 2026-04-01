FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY hive/ /app/hive/

CMD ["python", "-m", "hive.agents.tier1"]
