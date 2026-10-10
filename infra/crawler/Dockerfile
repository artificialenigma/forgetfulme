FROM unclecode/crawl4ai:0.9.4@sha256:9021b3cb5c6f12570bbcd5395638495e0a06969b3148e377b953d174af2ebc9b
USER root
# Stay on the upstream Debian release; apply its available package updates.
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
# Update extraction/security packages; retain the matching reviewed server.
RUN python -m pip uninstall --yes jwt PyJWT litellm \
    && python -m pip install --no-cache-dir 'crawl4ai==0.9.4' 'anyio==4.14.2' 'nltk==3.10.3' 'PyJWT==2.14.0' 'urllib3==2.8.0' 'chardet==5.2.0' \
    && python -m pip check
COPY server-requirements.txt /tmp/server-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/server-requirements.txt && python -m pip check
COPY upstream-server/ /app/
# Retain our existing expiration requirement with upstream's broader auth gate.
RUN python -c "from pathlib import Path; p=Path('/app/auth.py'); s=p.read_text(); old='jwt.decode(token, SECRET_KEY, algorithms=_ALGORITHMS)'; assert s.count(old)==1; p.write_text(s.replace(old, 'jwt.decode(token, SECRET_KEY, algorithms=_ALGORITHMS, options={\"require\": [\"exp\"]})'))" \
    && mkdir -p /var/lib/redis /var/log/redis /var/lib/crawl4ai \
    && chown -R appuser:appuser /var/lib/redis /var/log/redis /var/lib/crawl4ai \
    && chmod +x /app/entrypoint.sh
# Run supervisor on the maintained Python interpreter instead of Debian Python 3.11.
RUN python -m pip install --no-cache-dir 'supervisor==4.3.0' \
    && python -m pip check \
    && apt-get purge -y python3.11 python3.11-minimal libpython3.11 libpython3.11-minimal libpython3.11-stdlib libpython3.11-dev python3.11-dev supervisor \
    && test "$(command -v supervisord)" = /usr/local/bin/supervisord \
    && test ! -e /usr/bin/python3.11
# Match upstream runtime identity so supervised workers use /home/appuser.
USER appuser
RUN python -m playwright install chromium --only-shell

ENTRYPOINT ["/app/entrypoint.sh"]
CMD []
