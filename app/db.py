import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row


def connect():
    if os.environ.get("FM_TEST_ISOLATED"):
        _check_test_settings()
    return psycopg.connect(host=os.environ.get("PGHOST", "db"),
                           port=os.environ.get("PGPORT", "5432"),
                           dbname=os.environ.get("PGDATABASE", "forgetfulme"),
                           user=os.environ.get("PGUSER", "forgetfulme"),
                           password=os.environ["POSTGRES_PASSWORD"], row_factory=dict_row,
                           connect_timeout=5)


def _check_test_settings():
    """Fail closed before connecting if disposable-test settings are incomplete."""
    expected = {"FM_TEST_ISOLATED": "1", "PGHOST": "test-db",
                "PGDATABASE": "forgetfulme_test", "PGUSER": "test_runner"}
    if (any(os.environ.get(key) != value for key, value in expected.items())
            or os.environ.get("PGPORT", "5432") != "5432"
            or any(os.environ.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"))):
        raise RuntimeError("Mutating tests require the disposable Compose harness")


def require_isolated_test():
    """Guard mutating fixtures against production defaults and the real vault."""
    _check_test_settings()
    token = os.environ.get("FM_TEST_RUN_ID", "")
    marker = Path("/vault/.forgetfulme-isolated-test")
    if not token or not marker.is_file() or marker.read_text().strip() != token:
        raise RuntimeError("Disposable test vault marker is missing or mismatched")
    with connect() as db:
        identity = db.execute("SELECT current_database() AS name, current_user AS role").fetchone()
    if identity != {"name": "forgetfulme_test", "role": "test_runner"}:
        raise RuntimeError("Refusing to mutate a database outside the disposable harness")
