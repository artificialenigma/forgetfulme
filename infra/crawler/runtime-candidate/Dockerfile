# Experimental runtime reduction; deploy only after the full modern API matrix.
FROM forgetfulme-crawler:local@sha256:35eabc8e6da154873a6846bf95e6d11bb5bb1a97d129fa3d1efad21ba8bf81fe
USER root
# Supervisor 4.3 supports Python 3.12 without the legacy pkg_resources dependency.
RUN python -m pip install --no-cache-dir 'supervisor==4.3.0' \
    && python -m pip check \
    && apt-get purge -y python3.11 python3.11-minimal libpython3.11 libpython3.11-minimal libpython3.11-stdlib libpython3.11-dev python3.11-dev supervisor \
    && test "$(command -v supervisord)" = /usr/local/bin/supervisord \
    && test ! -e /usr/bin/python3.11
USER appuser
