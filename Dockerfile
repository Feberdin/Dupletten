# Zweck:
#   Baut einen kleinen Container fuer das Arr-Duplikat-Dashboard.
# Input/Output:
#   Installiert Python-Abhaengigkeiten, kopiert die App und startet den
#   Webserver auf Port 8000.
# Wichtige Invarianten:
#   Secrets werden nur per Environment uebergeben, nie ins Image geschrieben.
# Debugging:
#   Bei Build-Problemen zuerst `docker build .` lokal pruefen und danach
#   `docker logs` fuer Laufzeitfehler verwenden.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY README.md /app/README.md

EXPOSE 8000

CMD ["python", "-m", "app"]
