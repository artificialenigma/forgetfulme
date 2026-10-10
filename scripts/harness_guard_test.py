"""Prove mutating test guards reject production defaults before connecting."""
import os
from unittest.mock import patch
from app import db

db.require_isolated_test()
actual = dict(os.environ)
cases = [
    {},
    {**actual, 'FM_TEST_ISOLATED': '0'},
    {**actual, 'PGHOST': 'db'},
    {**actual, 'PGDATABASE': 'forgetfulme'},
    {**actual, 'PGUSER': 'forgetfulme'},
    {**actual, 'PGPORT': '15432'},
    {**actual, 'PGHOSTADDR': '127.0.0.1'},
    {**actual, 'PGSERVICE': 'production'},
    {**actual, 'FM_TEST_RUN_ID': ''},
    {**actual, 'FM_TEST_RUN_ID': 'wrong-vault-marker'},
]
for environment in cases:
    with patch.dict(os.environ, environment, clear=True), patch.object(db, 'connect', side_effect=AssertionError('Guard attempted a database connection')):
        try:
            db.require_isolated_test()
        except RuntimeError:
            pass
        else:
            raise AssertionError('Unsafe fixture configuration was accepted')
with patch.dict(os.environ, {**actual, 'PGHOST': 'db'}, clear=True), patch.object(db.psycopg, 'connect', side_effect=AssertionError('Unsafe test connector reached PostgreSQL')):
    try:
        db.connect()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Test connector accepted a production host')
print('Isolation guards reject default/production settings and missing/mismatched vault markers before any database connection')
