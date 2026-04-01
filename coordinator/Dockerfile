FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY hive/ /app/hive/

EXPOSE 8000

CMD ["uvicorn", "hive.coordinator.app:app", "--host", "0.0.0.0", "--port", "8000"]
