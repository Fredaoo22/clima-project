# Clima Project

Pipeline de ingestao de previsao do OpenWeather para Oracle, com carga incremental e limpeza de janela de previsoes.

## Estrutura do projeto

```text
clima-project/
├── src/
│   ├── openweather/
│   │   ├── carga_openweather.py
│   │   └── README.md
│   └── database/
│       └── migracao_dim_tempo_hora.sql
├── data/
│   └── raw/
├── notebooks/
├── requirements-openweather.txt
├── .env.openweather.example
└── .github/workflows/openweather-carga.yml
```

## Setup rapido

1. Instale dependencias:
   ```bash
   python3 -m pip install -r requirements-openweather.txt
   ```
2. Crie o arquivo de configuracao local:
   ```bash
   cp .env.openweather.example .env.openweather
   ```
3. Edite `.env.openweather` com credenciais reais e caminho da wallet.

## Execucao local

```bash
python3 src/openweather/carga_openweather.py --limit-cidades 10
```

## Observacoes

- O script valida se `ORACLE_DSN` existe no `tnsnames.ora` quando wallet estiver configurada.
- `ORACLE_CONFIG_DIR` e `ORACLE_WALLET_LOCATION` devem apontar para a pasta da wallet.
- Estado de retomada fica em `.openweather_checkpoint.json`.
