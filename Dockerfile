# Usa a imagem oficial do Apache Airflow como base
FROM apache/airflow:2.9.1

# Define o usuário root apenas para eventuais atualizações de sistema operacional
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         build-essential \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Volta para o usuário oficial do airflow para segurança
USER airflow

# Copia apenas o arquivo de dependências para dentro da imagem
COPY requirements-openweather.txt /

# Instala o OracleDB e o Requests dentro do ambiente do Airflow
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements-openweather.txt
