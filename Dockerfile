FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home colonia && mkdir /data && chown colonia:colonia /data
COPY --chown=colonia:colonia . .
ENV COLONIA_DB=/data/colonia.sqlite3 PYTHONUNBUFFERED=1
USER colonia
EXPOSE 8000
CMD ["python", "start.py"]
