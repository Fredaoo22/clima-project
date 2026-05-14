#!/usr/bin/env python3
"""Carga automatizada de previsao OpenWeather para Oracle.

Fluxo:
1) Ler cidades com latitude/longitude em DIM_CIDADE
2) Buscar previsao 5 dias / 3 horas no OpenWeather
3) Garantir datas na DIM_TEMPO
4) Upsert na FATO_CLIMA por (CIDADE_ID, DATA_COLETA)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import oracledb
import requests

OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
DELETE_FORA_JANELA_SQL = """
DELETE FROM FATO_CLIMA
WHERE DATA_COLETA < TRUNC(CURRENT_DATE)
   OR DATA_COLETA >= TRUNC(CURRENT_DATE) + :1
"""
DB_RECOVERABLE_MARKERS = (
  "DPY-1001",
  "DPY-4011",
  "ORA-03113",
  "ORA-03114",
  "ORA-12541",
  "ORA-12545",
  "ORA-12170",
  "Connection reset by peer",
  "connection was closed",
)

FETCH_CIDADES_SQL = """
SELECT CIDADE_ID, CIDADE_NOME, LATITUDE, LONGITUDE
FROM DIM_CIDADE
WHERE LATITUDE IS NOT NULL
  AND LONGITUDE IS NOT NULL
ORDER BY CIDADE_ID
"""

MERGE_DIM_TEMPO_SQL = """
MERGE INTO DIM_TEMPO d
USING (SELECT :1 AS DATA_COMPLETA FROM dual) s
ON (d.TEMPO_ID = TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'YYYYMMDD')))
WHEN NOT MATCHED THEN INSERT (
  TEMPO_ID,
  DATA_COMPLETA,
  DIA_NUMERO,
  DIA_NOME,
  DIA_SEMANA_NUMERO,
  EH_FIM_SEMANA,
  MES_NUMERO,
  MES_NOME,
  TRIMESTRE_NUMERO,
  SEMESTRE_NUMERO,
  ANO_NUMERO,
  ANO_MES
) VALUES (
  TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'YYYYMMDD')),
  s.DATA_COMPLETA,
  TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'DD')),
  INITCAP(TO_CHAR(s.DATA_COMPLETA, 'FMDAY', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
  (TRUNC(s.DATA_COMPLETA) - TRUNC(s.DATA_COMPLETA, 'IW') + 1),
  CASE WHEN (TRUNC(s.DATA_COMPLETA) - TRUNC(s.DATA_COMPLETA, 'IW') + 1) IN (6, 7) THEN 1 ELSE 0 END,
  TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'MM')),
  INITCAP(TO_CHAR(s.DATA_COMPLETA, 'FMMONTH', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
  TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'Q')),
  CASE WHEN TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'MM')) <= 6 THEN 1 ELSE 2 END,
  TO_NUMBER(TO_CHAR(s.DATA_COMPLETA, 'YYYY')),
  TO_CHAR(s.DATA_COMPLETA, 'YYYY-MM')
)
"""

MERGE_FATO_CLIMA_SQL = """
MERGE INTO FATO_CLIMA f
USING (
  SELECT
    :1 AS CIDADE_ID,
    :2 AS DATA_COLETA,
    :3 AS TEMPERATURA_MIN,
    :4 AS TEMPERATURA_MAX,
    :5 AS SENSACAO_TERMICA,
    :6 AS UMIDADE,
    :7 AS VENTO_VELOCIDADE,
    :8 AS CHUVA_PROBABILIDADE,
    :9 AS DESCRICAO_CLIMA,
    :10 AS TEMPO_ID,
    :11 AS HORA_MINUTO_ID
  FROM dual
) s
ON (
  f.CIDADE_ID = s.CIDADE_ID
  AND f.DATA_COLETA = s.DATA_COLETA
)
WHEN MATCHED THEN UPDATE SET
  f.TEMPERATURA_MIN = s.TEMPERATURA_MIN,
  f.TEMPERATURA_MAX = s.TEMPERATURA_MAX,
  f.SENSACAO_TERMICA = s.SENSACAO_TERMICA,
  f.UMIDADE = s.UMIDADE,
  f.VENTO_VELOCIDADE = s.VENTO_VELOCIDADE,
  f.CHUVA_PROBABILIDADE = s.CHUVA_PROBABILIDADE,
  f.DESCRICAO_CLIMA = s.DESCRICAO_CLIMA,
  f.TEMPO_ID = s.TEMPO_ID,
  f.HORA_MINUTO_ID = s.HORA_MINUTO_ID
WHEN NOT MATCHED THEN INSERT (
  CIDADE_ID,
  DATA_COLETA,
  TEMPERATURA_MIN,
  TEMPERATURA_MAX,
  SENSACAO_TERMICA,
  UMIDADE,
  VENTO_VELOCIDADE,
  CHUVA_PROBABILIDADE,
  DESCRICAO_CLIMA,
  TEMPO_ID,
  HORA_MINUTO_ID
) VALUES (
  s.CIDADE_ID,
  s.DATA_COLETA,
  s.TEMPERATURA_MIN,
  s.TEMPERATURA_MAX,
  s.SENSACAO_TERMICA,
  s.UMIDADE,
  s.VENTO_VELOCIDADE,
  s.CHUVA_PROBABILIDADE,
  s.DESCRICAO_CLIMA,
  s.TEMPO_ID,
  s.HORA_MINUTO_ID
)
"""


@dataclass(frozen=True)
class Cidade:
  cidade_id: int
  cidade_nome: str
  latitude: float
  longitude: float


@dataclass(frozen=True)
class Config:
  api_key: str
  oracle_user: str
  oracle_password: str
  oracle_dsn: str
  oracle_config_dir: str | None
  oracle_wallet_location: str | None
  oracle_wallet_password: str | None
  units: str
  lang: str
  timeout_seconds: int
  sleep_seconds: float
  limit_cidades: int
  commit_every: int
  window_timezone: str
  window_days_ahead: int
  db_max_retries: int
  db_retry_seconds: float
  api_max_retries: int
  api_retry_seconds: float
  checkpoint_file: str
  resume_enabled: bool
  simulate_crash: int


def _required_env(name: str) -> str:
  value = os.getenv(name)
  if not value:
    raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
  return value


def load_local_env_file() -> None:
  """Carrega variaveis de .env.openweather sem sobrescrever env ja definido."""
  repo_root = Path(__file__).resolve().parents[2]
  candidatos = [
    Path.cwd() / ".env.openweather",
    repo_root / ".env.openweather",
  ]

  arquivo = next((p for p in candidatos if p.exists()), None)
  if arquivo is None:
    return

  for raw in arquivo.read_text(encoding="utf-8").splitlines():
    linha = raw.strip()
    if not linha or linha.startswith("#") or "=" not in linha:
      continue
    chave, valor = linha.split("=", 1)
    chave = chave.strip()
    valor = valor.strip().strip("'").strip('"')
    if chave and chave not in os.environ:
      os.environ[chave] = valor


def _is_placeholder_path(path: str) -> bool:
  valor = path.strip().lower()
  return "/caminho/para/" in valor or "<pasta_wallet" in valor


def _looks_like_dsn_alias(dsn: str) -> bool:
  return all(token not in dsn for token in ("/", ":", "(", ")", "="))


def _read_tns_aliases(tns_path: Path) -> set[str]:
  aliases: set[str] = set()
  pattern = re.compile(r"^[A-Za-z0-9_.-]+$")
  for raw in tns_path.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    name = line.split("=", 1)[0].strip()
    if pattern.match(name):
      aliases.add(name.lower())
  return aliases


def _validate_oracle_wallet_config(cfg: Config) -> None:
  if cfg.oracle_config_dir and _is_placeholder_path(cfg.oracle_config_dir):
    raise RuntimeError(
      "ORACLE_CONFIG_DIR ainda esta com placeholder (/caminho/para/wallet). "
      "Use o caminho real da pasta da wallet."
    )
  if cfg.oracle_wallet_location and _is_placeholder_path(cfg.oracle_wallet_location):
    raise RuntimeError(
      "ORACLE_WALLET_LOCATION ainda esta com placeholder (/caminho/para/wallet). "
      "Use o caminho real da pasta da wallet."
    )

  if bool(cfg.oracle_config_dir) != bool(cfg.oracle_wallet_location):
    raise RuntimeError(
      "Defina ORACLE_CONFIG_DIR e ORACLE_WALLET_LOCATION juntos ao usar wallet."
    )

  if not cfg.oracle_config_dir:
    return

  config_dir = Path(cfg.oracle_config_dir).expanduser()
  wallet_dir = Path(cfg.oracle_wallet_location or "").expanduser()
  if not config_dir.is_dir():
    raise RuntimeError(f"ORACLE_CONFIG_DIR nao existe ou nao e pasta: {config_dir}")
  if not wallet_dir.is_dir():
    raise RuntimeError(f"ORACLE_WALLET_LOCATION nao existe ou nao e pasta: {wallet_dir}")

  tns_path = config_dir / "tnsnames.ora"
  if not tns_path.is_file():
    raise RuntimeError(f"Arquivo tnsnames.ora nao encontrado em ORACLE_CONFIG_DIR: {tns_path}")

  if _looks_like_dsn_alias(cfg.oracle_dsn):
    aliases = _read_tns_aliases(tns_path)
    if cfg.oracle_dsn.lower() not in aliases:
      disponiveis = ", ".join(sorted(aliases)) if aliases else "(nenhum alias encontrado)"
      raise RuntimeError(
        "ORACLE_DSN nao encontrado no tnsnames.ora de ORACLE_CONFIG_DIR. "
        f"Recebido: {cfg.oracle_dsn}. Aliases disponiveis: {disponiveis}"
      )


def _is_coordinate_in_range(valor: float, tipo: str) -> bool:
  limite = 90.0 if tipo == "lat" else 180.0
  return abs(float(valor)) <= limite


def load_config(args: argparse.Namespace) -> Config:
  load_local_env_file()
  repo_root = Path(__file__).resolve().parents[2]
  cfg = Config(
    api_key=_required_env("OPENWEATHER_API_KEY"),
    oracle_user=_required_env("ORACLE_USER"),
    oracle_password=_required_env("ORACLE_PASSWORD"),
    oracle_dsn=_required_env("ORACLE_DSN"),
    oracle_config_dir=os.getenv("ORACLE_CONFIG_DIR"),
    oracle_wallet_location=os.getenv("ORACLE_WALLET_LOCATION"),
    oracle_wallet_password=os.getenv("ORACLE_WALLET_PASSWORD"),
    units=os.getenv("OWM_UNITS", "metric"),
    lang=os.getenv("OWM_LANG", "pt_br"),
    timeout_seconds=int(os.getenv("OWM_TIMEOUT_SECONDS", "20")),
    sleep_seconds=float(os.getenv("OWM_SLEEP_SECONDS", str(args.sleep_seconds))),
    limit_cidades=args.limit_cidades,
    commit_every=args.commit_every,
    window_timezone=os.getenv("OWM_WINDOW_TIMEZONE", "America/Sao_Paulo"),
    window_days_ahead=int(os.getenv("OWM_WINDOW_DAYS_AHEAD", "5")),
    db_max_retries=int(os.getenv("OWM_DB_MAX_RETRIES", "3")),
    db_retry_seconds=float(os.getenv("OWM_DB_RETRY_SECONDS", "3")),
    api_max_retries=int(os.getenv("OWM_API_MAX_RETRIES", "2")),
    api_retry_seconds=float(os.getenv("OWM_API_RETRY_SECONDS", "2")),
    checkpoint_file=os.getenv(
      "OWM_CHECKPOINT_FILE",
      str(repo_root / ".openweather_checkpoint.json"),
    ),
    resume_enabled=not args.no_resume,
    simulate_crash=args.simulate_crash,
  )
  _validate_oracle_wallet_config(cfg)
  return cfg


def fetch_cidades(cursor: oracledb.Cursor, limit_cidades: int) -> List[Cidade]:
  cursor.execute(FETCH_CIDADES_SQL)
  cidades: List[Cidade] = []
  descartadas = 0

  for r in cursor.fetchall():
    cidade_id = int(r[0])
    cidade_nome = str(r[1])
    lat = float(r[2])
    lon = float(r[3])

    if not _is_coordinate_in_range(lat, "lat") or not _is_coordinate_in_range(lon, "lon"):
      descartadas += 1
      print(
        f"[WARN] Cidade descartada por coordenada fora da faixa valida "
        f"cidade_id={cidade_id} nome={cidade_nome} lat={lat} lon={lon}",
        file=sys.stderr,
      )
      continue

    cidades.append(Cidade(cidade_id, cidade_nome, lat, lon))

  if descartadas > 0:
    print(f"[INFO] Cidades descartadas por coordenada fora da faixa: {descartadas}.")

  if limit_cidades > 0:
    cidades = cidades[:limit_cidades]
  return cidades


def _safe_tz_literal(tz: str) -> str:
  permitido = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/_:+-")
  if not tz or any(ch not in permitido for ch in tz):
    raise ValueError(
      "OWM_WINDOW_TIMEZONE invalido. Use algo como America/Sao_Paulo ou -03:00."
    )
  return tz


def purge_outside_window(cursor: oracledb.Cursor, cfg: Config) -> int:
  tz = _safe_tz_literal(cfg.window_timezone)
  dias_manter = cfg.window_days_ahead + 1

  cursor.execute(f"ALTER SESSION SET TIME_ZONE = '{tz}'")
  cursor.execute(DELETE_FORA_JANELA_SQL, [dias_manter])
  return int(cursor.rowcount or 0)


def _is_db_recoverable_error(exc: Exception) -> bool:
  msg = str(exc)
  return any(marker in msg for marker in DB_RECOVERABLE_MARKERS)


def _close_quietly(obj: object) -> None:
  if obj is None:
    return
  close_fn = getattr(obj, "close", None)
  if callable(close_fn):
    try:
      close_fn()
    except Exception:  # noqa: BLE001
      pass


def _build_connect_kwargs(cfg: Config) -> dict:
  kwargs = {
    "user": cfg.oracle_user,
    "password": cfg.oracle_password,
    "dsn": cfg.oracle_dsn,
  }
  if cfg.oracle_config_dir:
    kwargs["config_dir"] = cfg.oracle_config_dir
  if cfg.oracle_wallet_location:
    kwargs["wallet_location"] = cfg.oracle_wallet_location
  if cfg.oracle_wallet_password:
    kwargs["wallet_password"] = cfg.oracle_wallet_password
  return kwargs


def _connect_database(cfg: Config) -> oracledb.Connection:
  kwargs = _build_connect_kwargs(cfg)
  return oracledb.connect(**kwargs)


def _load_checkpoint(path: Path) -> dict | None:
  if not path.exists():
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except Exception:  # noqa: BLE001
    return None
  return data if isinstance(data, dict) else None


def _save_checkpoint(path: Path, *, next_index: int, total_cidades: int, cidade_id: int) -> None:
  payload = {
    "version": 1,
    "next_index": int(next_index),
    "total_cidades": int(total_cidades),
    "last_cidade_id": int(cidade_id),
    "updated_at": datetime.now(timezone.utc).isoformat(),
  }
  path.parent.mkdir(parents=True, exist_ok=True)
  temp_path = path.with_suffix(path.suffix + ".tmp")
  temp_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
  temp_path.replace(path)


def _clear_checkpoint(path: Path) -> None:
  try:
    path.unlink(missing_ok=True)
  except Exception:  # noqa: BLE001
    pass


def to_local_datetime(utc_unix: int, timezone_offset_seconds: int) -> datetime:
  utc_dt = datetime.fromtimestamp(int(utc_unix), tz=timezone.utc)
  local_dt = utc_dt + timedelta(seconds=int(timezone_offset_seconds))
  return local_dt.replace(tzinfo=None)


def normalize_forecast_rows(cidade_id: int, payload: dict) -> Tuple[List[Tuple], List[date]]:
  timezone_offset = int(payload.get("city", {}).get("timezone", 0))
  lista = payload.get("list", [])

  fato_rows: List[Tuple] = []
  datas_dim: List[date] = []

  for item in lista:
    dt_unix = item.get("dt")
    if dt_unix is None:
      continue

    dt_local = to_local_datetime(int(dt_unix), timezone_offset)
    data_local = dt_local.date()

    main = item.get("main", {})
    wind = item.get("wind", {})
    weather = item.get("weather", [])

    temperatura_min = main.get("temp_min")
    temperatura_max = main.get("temp_max")
    sensacao_termica = main.get("feels_like")
    umidade = main.get("humidity")
    vento_velocidade = wind.get("speed")

    pop = item.get("pop")
    chuva_probabilidade = None if pop is None else round(float(pop) * 100, 2)

    descricao = None
    if weather:
      descricao = weather[0].get("description")

    tempo_id = int(dt_local.strftime("%Y%m%d"))
    hora_minuto_id = (dt_local.hour * 60) + dt_local.minute + 1

    fato_rows.append(
      (
        cidade_id,
        dt_local,
        temperatura_min,
        temperatura_max,
        sensacao_termica,
        umidade,
        vento_velocidade,
        chuva_probabilidade,
        descricao,
        tempo_id,
        hora_minuto_id,
      )
    )
    datas_dim.append(data_local)

  return fato_rows, datas_dim


def ensure_dim_tempo(cursor: oracledb.Cursor, datas: Iterable[date]) -> None:
  unicas = sorted(set(datas))
  if not unicas:
    return

  binds = [(datetime.combine(d, datetime.min.time()),) for d in unicas]
  cursor.executemany(MERGE_DIM_TEMPO_SQL, binds)


def fetch_forecast(session: requests.Session, cfg: Config, cidade: Cidade) -> dict:
  params = {
    "lat": cidade.latitude,
    "lon": cidade.longitude,
    "appid": cfg.api_key,
    "units": cfg.units,
    "lang": cfg.lang,
  }
  resp = session.get(OPENWEATHER_FORECAST_URL, params=params, timeout=cfg.timeout_seconds)
  resp.raise_for_status()
  payload = resp.json()
  cod = str(payload.get("cod", ""))
  if cod and cod != "200":
    msg = payload.get("message", "erro sem detalhe")
    raise RuntimeError(f"OpenWeather retornou cod={cod}: {msg}")
  return payload


def fetch_forecast_with_retry(session: requests.Session, cfg: Config, cidade: Cidade) -> dict:
  tentativas = max(0, cfg.api_max_retries) + 1
  for tentativa in range(1, tentativas + 1):
    try:
      return fetch_forecast(session, cfg, cidade)
    except requests.RequestException as exc:
      if tentativa == tentativas:
        raise
      espera = cfg.api_retry_seconds * tentativa
      print(
        f"[WARN] Falha HTTP cidade_id={cidade.cidade_id} tentativa={tentativa}/{tentativas} "
        f"detalhe={exc}. Aguardando {espera:.1f}s para retry...",
        file=sys.stderr,
      )
      time.sleep(espera)


def run(cfg: Config) -> int:
  try:
    conexao = _connect_database(cfg)
  except socket.gaierror as exc:
    raise RuntimeError(
      "Falha ao resolver host do ORACLE_DSN. "
      "Confira se o host esta correto e no formato host:porta/servico "
      "(ex.: localhost:1521/XEPDB1)."
    ) from exc

  cursor: oracledb.Cursor | None = None
  session = requests.Session()

  total_cidades = 0
  ok_cidades = 0
  erro_cidades = 0
  total_fatos = 0
  linhas_removidas = 0
  commits_pendentes = 0
  checkpoint_path = Path(cfg.checkpoint_file)
  start_index = 0
  last_processed_next_index = 0
  last_processed_cidade_id = 0

  try:
    cursor = conexao.cursor()
    cidades = fetch_cidades(cursor, cfg.limit_cidades)
    total_cidades = len(cidades)
    if total_cidades == 0:
      print("Nenhuma cidade com lat/lon encontrada em DIM_CIDADE.")
      return 0

    if not cfg.resume_enabled:
      _clear_checkpoint(checkpoint_path)
    else:
      checkpoint = _load_checkpoint(checkpoint_path)
      if checkpoint:
        next_index = checkpoint.get("next_index")
        total_checkpoint = checkpoint.get("total_cidades")
        if (
          isinstance(next_index, int)
          and isinstance(total_checkpoint, int)
          and total_checkpoint == total_cidades
          and 0 < next_index < total_cidades
        ):
          start_index = next_index
          print(
            f"[INFO] Retomando do checkpoint: cidade {start_index + 1}/{total_cidades}."
          )
        elif isinstance(next_index, int) and next_index >= total_cidades:
          _clear_checkpoint(checkpoint_path)
        else:
          print("[WARN] Checkpoint ignorado (incompativel com a carga atual).")

    for idx in range(start_index, total_cidades):
      cidade = cidades[idx]
      i = idx + 1
      
      # --- INICIO DO MODO CAOS ---
      if cfg.simulate_crash > 0 and i == cfg.simulate_crash and start_index == 0:
          print(f"🔥 [MODO CAOS ATIVADO] Simulando queda de energia antes de processar a cidade {i}...", file=sys.stderr)
          sys.exit(1)
      # --- FIM DO MODO CAOS ---

      try:
        payload = fetch_forecast_with_retry(session, cfg, cidade)
        fato_rows, datas_dim = normalize_forecast_rows(cidade.cidade_id, payload)

        tentativas_db = max(0, cfg.db_max_retries) + 1
        gravou = False
        for tentativa in range(1, tentativas_db + 1):
          try:
            ensure_dim_tempo(cursor, datas_dim)
            if fato_rows:
              cursor.executemany(MERGE_FATO_CLIMA_SQL, fato_rows)
              total_fatos += len(fato_rows)
            commits_pendentes += 1
            if commits_pendentes >= cfg.commit_every:
              conexao.commit()
              _save_checkpoint(
                checkpoint_path,
                next_index=idx + 1,
                total_cidades=total_cidades,
                cidade_id=cidade.cidade_id,
              )
              commits_pendentes = 0
            gravou = True
            break
          except Exception as db_exc:  # noqa: BLE001
            if not _is_db_recoverable_error(db_exc) or tentativa == tentativas_db:
              raise
            espera = cfg.db_retry_seconds * tentativa
            print(
              f"[WARN] Falha de conexao DB cidade_id={cidade.cidade_id} "
              f"tentativa={tentativa}/{tentativas_db} detalhe={db_exc}. "
              f"Reconectando em {espera:.1f}s...",
              file=sys.stderr,
            )
            _close_quietly(cursor)
            _close_quietly(conexao)
            time.sleep(espera)
            conexao = _connect_database(cfg)
            cursor = conexao.cursor()

        if not gravou:
          raise RuntimeError("Falha ao gravar registro no banco apos retries.")

        ok_cidades += 1
        print(
          f"[{i}/{total_cidades}] OK cidade_id={cidade.cidade_id} "
          f"nome={cidade.cidade_nome} registros={len(fato_rows)}"
        )

      except Exception as exc:  # noqa: BLE001
        erro_cidades += 1
        print(
          f"[{i}/{total_cidades}] ERRO cidade_id={cidade.cidade_id} "
          f"nome={cidade.cidade_nome} detalhe={exc}",
          file=sys.stderr,
        )

      last_processed_next_index = idx + 1
      last_processed_cidade_id = cidade.cidade_id
      time.sleep(cfg.sleep_seconds)

    tentativas_db = max(0, cfg.db_max_retries) + 1
    for tentativa in range(1, tentativas_db + 1):
      try:
        linhas_removidas = purge_outside_window(cursor, cfg)
        conexao.commit()
        _clear_checkpoint(checkpoint_path)
        commits_pendentes = 0
        break
      except Exception as db_exc:  # noqa: BLE001
        if not _is_db_recoverable_error(db_exc) or tentativa == tentativas_db:
          raise
        espera = cfg.db_retry_seconds * tentativa
        print(
          f"[WARN] Falha ao aplicar limpeza da janela tentativa={tentativa}/{tentativas_db} "
          f"detalhe={db_exc}. Reconectando em {espera:.1f}s...",
          file=sys.stderr,
        )
        _close_quietly(cursor)
        _close_quietly(conexao)
        time.sleep(espera)
        conexao = _connect_database(cfg)
        cursor = conexao.cursor()
  finally:
    if commits_pendentes > 0:
      try:
        conexao.commit()
        if last_processed_next_index > 0 and last_processed_cidade_id > 0:
          _save_checkpoint(
            checkpoint_path,
            next_index=last_processed_next_index,
            total_cidades=total_cidades,
            cidade_id=last_processed_cidade_id,
          )
      except Exception:  # noqa: BLE001
        pass
    _close_quietly(cursor)
    _close_quietly(conexao)
    session.close()

  print("=" * 60)
  print(f"Cidades lidas: {total_cidades}")
  print(f"Cidades OK: {ok_cidades}")
  print(f"Cidades com erro: {erro_cidades}")
  print(f"Registros upsert em FATO_CLIMA: {total_fatos}")
  print(
    "Registros removidos fora da janela "
    f"(hoje ate +{cfg.window_days_ahead} dias): {linhas_removidas}"
  )
  print("=" * 60)

  return 0 if erro_cidades == 0 else 1


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Carga OpenWeather -> Oracle")
  parser.add_argument(
    "--limit-cidades",
    type=int,
    default=0,
    help="Limita quantidade de cidades para teste (0 = todas)",
  )
  parser.add_argument(
    "--sleep-seconds",
    type=float,
    default=1.2,
    help="Pausa entre chamadas da API (segundos)",
  )
  parser.add_argument(
    "--commit-every",
    type=int,
    default=50,
    help="Frequencia de commit por quantidade de cidades",
  )
  parser.add_argument(
    "--no-resume",
    action="store_true",
    help="Ignora checkpoint salvo e recomeca do inicio.",
  )
  parser.add_argument(
    "--simulate-crash",
    type=int,
    default=0,
    help="Modo demonstracao: forca uma pane no sistema ao chegar na cidade X",
  )
  return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
  args = parse_args(argv)
  try:
    cfg = load_config(args)
  except Exception as exc:  # noqa: BLE001
    print(f"Erro de configuracao: {exc}", file=sys.stderr)
    return 2

  return run(cfg)


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
