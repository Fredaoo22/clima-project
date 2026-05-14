from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'visitante_github',
    'depends_on_past': False,
    'retries': 1, # Tenta rodar de novo 1 vez após a falha
    'retry_delay': timedelta(minutes=1), # Espera só 1 minuto pra pessoa não ficar entediada
}

with DAG(
    'demo_checkpoint_falha',
    default_args=default_args,
    description='DAG para demonstrar a recuperação de falhas no GitHub',
    schedule_interval=None, # Só roda quando a pessoa apertar Play
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['demo', 'github', 'teste'],
) as dag:

    # Limitamos a 20 cidades e mandamos o script "quebrar" na cidade 10
    demonstracao = BashOperator(
        task_id='simular_pane_e_recuperacao',
        bash_command='python3 /opt/airflow/src/openweather/carga_openweather.py --limit-cidades 20 --simulate-crash 10',
    )