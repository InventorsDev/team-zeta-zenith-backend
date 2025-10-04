FROM ghcr.io/samuelogboye/ml-base:2.8.0

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Copy (light) requirements and install only the rest (do NOT reinstall torch/transformers/spacy)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# create non-root user if not already set in base image
RUN mkdir -p models data logs && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
