from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'engenharia_de_dados',
    'depends_on_past': False,
    'email_on_failure': False,
    # Se a API cair ou o script quebrar, o Airflow tenta de novo até 10 vezes!
    'retries': 10,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    'pipeline_clima_openweather',
    default_args=default_args,
    description='ETL Diário de previsão do tempo pro Oracle DB',
    schedule_interval='0 6 * * *',
    start_date=datetime(2023, 1, 1),
    catchup=False,
    # Evita que o Airflow mate a tarefa por achar que demorou demais
    dagrun_timeout=timedelta(hours=4),
    tags=['etl', 'oracle', 'clima'],
) as dag:

    # O Airflow apenas aperta o Play. O Checkpoint é gerenciado pelo seu Python!
    rodar_carga = BashOperator(
        task_id='executar_script_python',
        bash_command='python3 /opt/airflow/src/openweather/carga_openweather.py',
    )
