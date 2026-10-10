FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG FM_APP_FINGERPRINT=unknown
LABEL com.forgetfulme.app_fingerprint=$FM_APP_FINGERPRINT
WORKDIR /srv
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && python -m pip uninstall --yes pip && useradd --uid 10001 --create-home app
COPY app ./app
RUN mkdir -p /data/content && chown -R app:app /data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
