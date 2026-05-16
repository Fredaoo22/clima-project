# ⛅ Pipeline ETL - Dados Climáticos em Larga Escala (OpenWeather & Oracle Cloud)

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/fred-henrique22)
[![Gmail](https://img.shields.io/badge/Gmail-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:fredsousa675@gmail.com)

> Pipeline ETL automatizado e resiliente para extração, transformação e armazenamento de previsões meteorológicas de mais de 5.000 cidades, utilizando Python, Apache Airflow, Docker e Oracle Autonomous Database para apoiar análises e dashboards em Power BI.

---

## 📋 Índice

* [Sobre o Projeto](#sobre-o-projeto)
* [Diferenciais de Engenharia](#diferenciais-de-engenharia)
* [Arquitetura do Pipeline](#arquitetura-do-pipeline)
* [Stack Tecnológica](#stack-tecnologica)
* [Modelagem de Dados (Star Schema)](#modelagem-de-dados)
* [Pré-requisitos](#pre-requisitos)
* [Instalação e Configuração](#instalacao-e-configuracao)
* [Como Executar e Testar Resiliência](#como-executar-e-testar-resiliencia)
* [Contato](#contato)

---

<a id="sobre-o-projeto"></a>

## 🎯 Sobre o Projeto

Este projeto demonstra a construção de um **pipeline ETL recorrente para dados climáticos**, desenhado para coletar previsões meteorológicas em larga escala e armazená-las em um modelo dimensional no **Oracle Autonomous Database**.

A solução utiliza uma base inicial de cidades e coordenadas, preparada a partir de dados do **IBGE** e de um CSV complementar de municípios brasileiros. Essa base é carregada no Oracle como dado de referência. A partir dela, o pipeline em **Python** consulta a API de previsão de 5 dias do **OpenWeather**, normaliza os retornos em JSON e realiza uma **carga incremental** no banco com `MERGE INTO`.

O resultado é uma base estruturada para consumo analítico, permitindo a construção de dashboards no **Power BI** com métricas como temperatura, sensação térmica, umidade, vento, probabilidade de chuva e análise por cidade, data e horário.

---

<a id="diferenciais-de-engenharia"></a>

## 🚀 Diferenciais de Engenharia

Ao contrário de uma carga simples e linear, este projeto foi estruturado com foco em **automação, confiabilidade e modelagem analítica**:

* **Orquestração com Apache Airflow:** a DAG agenda e monitora a execução diária do pipeline, com política de retries em caso de falha.
* **ETL em Python:** o Python Worker executa a extração das cidades no Oracle DB, coleta dados da OpenWeather API, transforma o JSON em registros tabulares e carrega os dados tratados no banco.
* **Checkpointing:** o pipeline salva o progresso em um arquivo `checkpoint.json`, permitindo retomar o processamento a partir da última cidade processada em caso de queda ou interrupção.
* **Upsert com MERGE INTO:** atualiza previsões existentes ou insere novos registros na `FATO_CLIMA`, evitando duplicidades por cidade e data de coleta.
* **Janela deslizante de previsões:** remove automaticamente registros fora da janela configurada, mantendo a base atualizada com previsões relevantes.
* **Validação de coordenadas:** descarta cidades com latitude ou longitude fora da faixa válida antes de consultar a API.
* **Modelagem dimensional:** organiza os dados em fato e dimensões, preparando a base para consultas analíticas e dashboards.

---


<a id="arquitetura-do-pipeline"></a>

## 🏗️ Arquitetura do Pipeline

---
<p align="center">
  <img src="https://github.com/user-attachments/assets/880fc845-366c-4cd5-9f99-5de43143a386" alt="Arquitetura do Pipeline" width="100%">
</p>

```text
Carga inicial de referência:

[ IBGE + CSV de municípios ]
            │
            ▼
[ Tratamento e validação em notebook ]
            │
            ▼
[ Oracle Autonomous Database ]
[ DIM_CIDADE / STG_CIDADE_GEO ]


ETL recorrente:

[ Apache Airflow ]
        │ agenda execução diária
        ▼
[ Python ETL Worker ] ───────► [ checkpoint.json ]
        │                          controle de retomada
        │
        ├── Extract
        │   ├─ Lê cidades e coordenadas no Oracle DB
        │   └─ Consulta previsões na OpenWeather API
        │
        ├── Transform
        │   └─ Normaliza JSON em registros tabulares,
        │      com datas, métricas climáticas e chaves de tempo
        │
        └── Load
            └─ MERGE/UPSERT em DIM_TEMPO e FATO_CLIMA


[ Oracle Autonomous Database ]
        │
        ▼
[ Power BI Dashboard ]
```

---

<a id="stack-tecnologica"></a>

## 🛠️ Stack Tecnológica

**Core**

* **Python 3** — lógica principal do ETL, tratamento do JSON, checkpoint e carga incremental.
* **Apache Airflow** — orquestração, agendamento e monitoramento da execução.
* **Docker & Docker Compose** — conteinerização do Airflow e ambiente local.
* **Oracle Autonomous Database** — armazenamento em nuvem e modelo dimensional.
* **Oracle Wallet** — autenticação segura com o banco Oracle Cloud.
* **Power BI** — consumo, visualização e análise dos dados climáticos.

**Bibliotecas Python**

* **requests** — chamadas HTTP para a API OpenWeather.
* **oracledb** — conexão e execução de comandos SQL no Oracle.
* **argparse** — parâmetros de execução via linha de comando.
* **dataclasses** — estruturação de configurações e entidades do pipeline.

---

<a id="modelagem-de-dados"></a>

## 🗄️ Modelagem de Dados (Star Schema)

O banco foi estruturado em um modelo dimensional para facilitar consultas analíticas e integração com Power BI.

* **FATO_CLIMA:** tabela fato com métricas climáticas como temperatura mínima, temperatura máxima, sensação térmica, umidade, velocidade do vento, probabilidade de chuva e descrição do clima.
* **DIM_CIDADE:** dimensão com informações das cidades, incluindo nome, UF, latitude, longitude e fuso horário.
* **DIM_ESTADO:** dimensão de estados brasileiros utilizada na organização geográfica.
* **DIM_TEMPO:** dimensão calendário com dia, mês, trimestre, semestre, ano, fim de semana e ano-mês.
* **DIM_HORA_MINUTO:** dimensão intradiária com granularidade de minuto, permitindo análises por horário e turno.
* **STG_CIDADE_GEO:** tabela de apoio para carga/atualização das coordenadas das cidades.

---

<a id="pre-requisitos"></a>

## ✅ Pré-requisitos

Antes de executar o projeto, é necessário ter:

* Docker e Docker Compose instalados.
* Conta e API Key no OpenWeather.
* Instância Oracle Autonomous Database criada.
* Arquivos da Oracle Wallet baixados e descompactados.
* SQL Developer, DBeaver ou ferramenta equivalente para executar os scripts SQL.
* Python 3 instalado, caso queira executar o script localmente fora do Airflow.

---

<a id="instalacao-e-configuracao"></a>

## 🚀 Instalação e Configuração

### 1. Clone o repositório

```bash
git clone https://github.com/Fredaoo22/clima-project.git
cd clima-project
```

### 2. Configure as variáveis de ambiente

Crie o arquivo de configuração local copiando o exemplo:

```bash
cp .env.openweather.example .env.openweather
```

Edite o arquivo `.env.openweather` com suas credenciais:

```ini
OPENWEATHER_API_KEY=sua_chave_api
ORACLE_USER=ADMIN
ORACLE_PASSWORD=sua_senha_do_banco
ORACLE_DSN=nome_do_banco_high
ORACLE_CONFIG_DIR=/opt/airflow/wallet
ORACLE_WALLET_LOCATION=/opt/airflow/wallet
ORACLE_WALLET_PASSWORD=senha_da_wallet
```

### 3. Configure a Oracle Wallet

Crie uma pasta chamada `Wallet_clima` na raiz do projeto e adicione nela os arquivos descompactados da Wallet do Oracle Autonomous Database.

A estrutura esperada é:

```text
clima-project/
├── Wallet_clima/
│   ├── tnsnames.ora
│   ├── sqlnet.ora
│   ├── cwallet.sso
│   └── demais arquivos da wallet
```

### 4. Inicialize a modelagem no Oracle

Execute os scripts SQL da pasta `src/database/` no Oracle:

```text
src/database/clima.sql
src/database/merge_lat_long.sql
src/database/migracao_dim_tempo_hora.sql
```

Esses scripts criam e ajustam as tabelas dimensionais, tabela fato e chaves necessárias para a modelagem analítica.

### 5. Suba a infraestrutura com Docker

```bash
mkdir -p logs
docker compose up airflow-init
docker compose up -d
```

---

<a id="como-executar-e-testar-resiliencia"></a>

## 🎮 Como Executar e Testar Resiliência

### 1. Acesse o Airflow

Abra no navegador:

```text
http://localhost:8080
```

Credenciais locais padrão:

```text
Usuário: admin
Senha: admin
```

### 2. Execute o pipeline principal

Ative a DAG:

```text
pipeline_clima_openweather
```

Ela executa o script:

```text
src/openweather/carga_openweather.py
```

O pipeline lê as cidades no Oracle, consulta a OpenWeather API, transforma os dados e realiza carga incremental no Oracle DB.

### 3. Execução local para teste

Também é possível executar o script manualmente:

```bash
python3 src/openweather/carga_openweather.py --limit-cidades 10
```

Para executar ignorando checkpoint salvo:

```bash
python3 src/openweather/carga_openweather.py --no-resume
```

### 4. Teste de resiliência com modo caos

O projeto possui um modo de simulação de falha para demonstrar retomada por checkpoint:

```bash
python3 src/openweather/carga_openweather.py --simulate-crash 10
```

Nesse cenário, o script simula uma interrupção durante o processamento. Na próxima execução, o checkpoint permite retomar o pipeline a partir do ponto salvo.

---

<a id="contato"></a>

## 📬 Contato

Desenvolvido por **Fred Henrique**, com foco em boas práticas de Engenharia de Dados, automação, modelagem dimensional e tolerância a falhas.

* **LinkedIn:** [linkedin.com/in/fred-henrique22](https://www.linkedin.com/in/fred-henrique22)
* **Email:** [fredsousa675@gmail.com](mailto:fredsousa675@gmail.com)
