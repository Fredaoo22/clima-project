🌤️ Pipeline ETL - Dados Climáticos em Larga Escala (OpenWeather & Oracle Cloud)
Pipeline ETL automatizado e resiliente para extração, processamento e armazenamento de previsões meteorológicas de mais de 5.000 cidades, alimentando um Data Warehouse na nuvem para análises em Power BI.

📋 Índice
Sobre o Projeto

Diferenciais de Engenharia

Arquitetura do Pipeline

Stack Tecnológica

Modelagem de Dados (Star Schema)

Pré-requisitos

Instalação e Configuração

Como Executar e Testar Resiliência

Contato

🎯 Sobre o Projeto
Este projeto demonstra a construção de um Pipeline ETL de nível de produção, desenhado para lidar com integrações de alto volume e interrupções de rede.

Ele consome a API de previsão de 5 dias (janelas de 3 horas) do OpenWeatherMap, normaliza os dados geográficos e climáticos, e realiza uma carga incremental em um banco Oracle Autonomous Database utilizando técnicas avançadas de UPSERT. O resultado é consumido por um dashboard no Power BI para visualização de tendências e padrões climáticos.

🚀 Diferenciais de Engenharia

Ao contrário de pipelines simples de extração linear, este projeto foi arquitetado com foco em confiabilidade:

Resiliência e Checkpointing: Em caso de queda de rede ou limite de cota da API no meio do processamento, o script salva o progresso localmente. Na próxima execução, ele retoma exatamente da cidade onde parou.

Upsert Inteligente (MERGE INTO): Atualiza previsões existentes ou insere novas, garantindo que não haja duplicidade na base.

Janela Deslizante (Purge): O próprio código gerencia o ciclo de vida dos dados, deletando automaticamente os registros históricos que caem fora da janela estipulada (+5 dias).

Auto-normalização Geográfica: Identifica e corrige automaticamente coordenadas geográficas recebidas fora de escala da base original.

🏗️ Arquitetura do Pipeline
Plaintext
    [ API OpenWeather ] (Previsões de 5 dias / 3 horas)
            │
            ▼ (Extração via HTTP com Exponential Backoff)
  ┌───────────────────┐
  │  PYTHON SCRIPT    │ 
  │ (Airflow Worker)  │ ──> [ Checkpoint.json ] (Salva estado a cada lote)
  └───────────────────┘
            │
            ▼ (Transformação e Upsert)
  ┌───────────────────┐
  │ ORACLE AUTONOMOUS │ ──> Autenticação segura via Oracle Wallet
  │    (Cloud DB)     │ 
  └───────────────────┘
            │
            ▼ (Modelagem Star Schema)
    [ POWER BI ] (Visualização de Dados e Time Intelligence)
Orquestração: Apache Airflow (Docker) rodando diariamente às 06:00.

🛠️ Stack Tecnológica
Core:

Python 3.12 — Processamento pesado e lógica de tolerância a falhas.

Apache Airflow 2.x — Orquestração e agendamento de tarefas em contêineres.

Oracle Autonomous Database — Data Warehouse na nuvem (Alta disponibilidade).

Docker & Docker Compose — Conteinerização do ambiente de orquestração.

Power BI — Consumo e visualização dos dados.

Bibliotecas Python:

requests — Chamadas HTTP.

oracledb — Driver nativo e de alta performance para o banco Oracle.

argparse & dataclasses — Estruturação e recebimento de parâmetros de linha de comando.

🗄️ Modelagem de Dados
O banco foi estruturado em Star Schema para otimizar a performance de leitura no Power BI, separando dimensões de data e hora para garantir análises de Time Intelligence.

FATO_CLIMA: Tabela central contendo as métricas métricas (temperatura, umidade, vento, etc.).

DIM_CIDADE: Tabela descritiva de localidades geográficas (Latitude, Longitude).

DIM_TEMPO: Dimensão calendário com granularidade diária (Ano, Mês, Fim de Semana).

DIM_HORA_MINUTO: Dimensão de tempo intraday (00:00 a 23:59), garantindo a segmentação precisa por turnos (Manhã, Tarde, Noite, Madrugada).

✅ Pré-requisitos
Docker e Docker Compose instalados.

Conta e API Key no OpenWeatherMap.

Instância de banco de dados Oracle Cloud e seus arquivos da Wallet baixados e descompactados.

SQL Developer ou DBeaver para rodar o script de inicialização no banco.

🚀 Instalação e Configuração
1. Clone o Repositório

Bash
git clone https://github.com/seu-usuario/clima-project.git
cd clima-project
2. Configure as Variáveis de Ambiente
Crie o arquivo na raiz do projeto copiando o exemplo:

Bash
cp .env.example .env.openweather
Edite o arquivo .env.openweather com suas credenciais:

Ini, TOML
OPENWEATHER_API_KEY=sua_chave_api
ORACLE_USER=ADMIN
ORACLE_PASSWORD=sua_senha_do_banco
ORACLE_DSN=nome_do_seu_banco_high
ORACLE_WALLET_PASSWORD=senha_da_sua_wallet
3. Autenticação Oracle (Wallet)
Crie uma pasta chamada Wallet_clima na raiz do projeto e cole todos os arquivos descompactados da sua Wallet da Oracle Cloud lá dentro.

4. Inicialize o Banco de Dados
Acesse o seu banco Oracle Cloud e execute o script sql/init_database.sql. Ele criará todas as tabelas (Star Schema) e inserirá as cidades iniciais para teste.

5. Suba a Infraestrutura (Docker)
Dê permissões para os arquivos de log e banco de dados local do Airflow, e suba os contêineres:

Bash
mkdir logs
chmod 777 logs src
docker compose up airflow-init
docker compose up -d
🎮 Como Executar
1. Acesse o Airflow
Abra http://localhost:8080 no navegador.

Usuário: admin | Senha: admin

2. O Fluxo de Produção (pipeline_clima_openweather)
Ligue a DAG principal. Ela rodará diariamente inserindo os dados silenciosamente no seu Data Warehouse.

🔥 3. Teste de Resiliência (Modo Caos)

Para provar a robustez do pipeline contra falhas de infraestrutura:

No Airflow, ligue e dispare a DAG demo_checkpoint_resiliencia.

Ela processará as primeiras cidades e simulará uma queda de sistema fatal na 10ª cidade.

A tarefa do Airflow falhará (UP_FOR_RETRY).

Um minuto depois, o Airflow reiniciará o contêiner e o Python lerá o Checkpoint, retornando a execução perfeitamente a partir da 10ª cidade até o fim. Acompanhe os Logs para ver a mágica acontecendo!

📬 Contato
Desenvolvido com foco em boas práticas de Engenharia de Dados e tolerância a falhas.

Autor: Fred Henrique

LinkedIn: www.linkedin.com/in/fred-henrique22

Email: fredsousa675@gmail.com
