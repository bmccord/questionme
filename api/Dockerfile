FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed.py .

# Non-root. The image holds no data and writes nothing.
RUN useradd --system --uid 10001 questionme
USER questionme

EXPOSE 4300
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4300"]
