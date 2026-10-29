# Image du pipeline FinGroup : Python + bibliotheques Google + dbt
FROM python:3.12-slim

# Pas de fichiers .pyc, logs affiches immediatement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Dependances d'abord : Docker garde cette couche en cache
#    tant que requirements.txt ne change pas (builds plus rapides)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Code du projet
COPY ingestion/ ingestion/
COPY dbt/ dbt/
COPY run_pipeline.py .

# Identifiants Google : fournis au lancement, jamais copies dans l'image
#   GCP_PROJECT_ID et GOOGLE_APPLICATION_CREDENTIALS (chemin vers une cle JSON)
CMD ["python", "run_pipeline.py"]
