FROM python:3.12-slim

WORKDIR /app

COPY sandbox/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-c", "print('Sandbox executor ready')"]
