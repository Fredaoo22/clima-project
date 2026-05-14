import os
import sys
from pathlib import Path
sys.path.insert(0, "/Users/Fredaoo/PORTIFOLIO/projects/clima-project/src/openweather")
import oracledb
from carga_openweather import load_config, fetch_cidades
import argparse

class DummyArgs:
    sleep_seconds = 0
    limit_cidades = 0
    commit_every = 1
    no_resume = True

cfg = load_config(DummyArgs())
kwargs = {
    "user": cfg.oracle_user,
    "password": cfg.oracle_password,
    "dsn": cfg.oracle_dsn,
    "config_dir": cfg.oracle_config_dir,
    "wallet_location": cfg.oracle_wallet_location,
}
try:
    conn = oracledb.connect(**kwargs)
    cursor = conn.cursor()
    cursor.execute("SELECT CIDADE_ID, LATITUDE, LONGITUDE FROM DIM_CIDADE WHERE CIDADE_ID IN (2687901, 2687958)")
    for r in cursor.fetchall():
        print(r)
except Exception as e:
    print(e)
