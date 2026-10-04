import os
import psycopg
from psycopg.rows import dict_row


def connect():
    return psycopg.connect(host="db", dbname="forgetfulme", user="forgetfulme",
                           password=os.environ["POSTGRES_PASSWORD"], row_factory=dict_row,
                           connect_timeout=5)
