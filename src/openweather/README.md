# Carga OpenWeather para Oracle

## O que o script faz
- Le todas as cidades com `LATITUDE` e `LONGITUDE` da `DIM_CIDADE`.
- Consulta a API `5 day / 3 hour forecast` do OpenWeather.
- Garante as datas na `DIM_TEMPO`.
- Faz upsert na `FATO_CLIMA` por `(CIDADE_ID, DATA_COLETA)`.
- Valida apenas faixa de coordenadas (`LATITUDE` entre `-90` e `90`, `LONGITUDE` entre `-180` e `180`).
- Remove da `FATO_CLIMA` previsoes fora da janela (hoje ate +5 dias, por padrao).

## Variaveis obrigatorias
- `OPENWEATHER_API_KEY`
- `ORACLE_USER`
- `ORACLE_PASSWORD`
- `ORACLE_DSN`

### Opcao B: Oracle Autonomous com Wallet
- `ORACLE_DSN=<alias_do_tnsnames.ora>` (ex.: `clima_high`)
- `ORACLE_CONFIG_DIR=<pasta_wallet_descompactada>`
- `ORACLE_WALLET_LOCATION=<pasta_wallet_descompactada>`
- `ORACLE_WALLET_PASSWORD` (se sua wallet exigir)

## Outras variaveis opcionais
- `OWM_UNITS` (padrao: `metric`)
- `OWM_LANG` (padrao: `pt_br`)
- `OWM_TIMEOUT_SECONDS` (padrao: `20`)
- `OWM_SLEEP_SECONDS` (padrao: `1.2`)
- `OWM_WINDOW_TIMEZONE` (padrao: `America/Sao_Paulo`)
- `OWM_WINDOW_DAYS_AHEAD` (padrao: `5`)

## Instalar dependencias
```bash
python3 -m pip install -r requirements-openweather.txt
```

## Preparar ambiente local
1. Copie o exemplo para o arquivo real:
```bash
cp .env.openweather.example .env.openweather
```
2. Ajuste os valores reais no `.env.openweather`.
3. Se usar wallet, confirme que:
   - `ORACLE_CONFIG_DIR` e `ORACLE_WALLET_LOCATION` apontam para a pasta da wallet.
   - `ORACLE_DSN` existe no `tnsnames.ora` (por exemplo: `clima_high`).

## Rodar local
```bash
python3 src/openweather/carga_openweather.py --limit-cidades 10
```

## Dica de diagnostico para wallet
Se `ORACLE_DSN` for alias, ele precisa existir no `tnsnames.ora` dentro da pasta indicada por `ORACLE_CONFIG_DIR`.

## Tolerancia a falhas de rede (opcional)
- `OWM_DB_MAX_RETRIES` (padrao: `3`) retries de reconexao com Oracle
- `OWM_DB_RETRY_SECONDS` (padrao: `3`) backoff base (segundos)
- `OWM_API_MAX_RETRIES` (padrao: `2`) retries para falhas HTTP
- `OWM_API_RETRY_SECONDS` (padrao: `2`) backoff base (segundos)
- `OWM_CHECKPOINT_FILE` caminho do arquivo de checkpoint para retomada

## Retomar apos queda
- Ao rodar novamente, o script retoma automaticamente do checkpoint salvo.
- Para ignorar checkpoint e recomecar do inicio:
```bash
python3 src/openweather/carga_openweather.py --no-resume
```
