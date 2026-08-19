"""Version 2 processing orchestration for the local-only pipeline."""

from __future__ import annotations

import datetime
import os

try:
    import pendulum
    from airflow.decorators import dag
    from airflow.operators.bash import BashOperator
    from airflow.operators.trigger_dagrun import TriggerDagRunOperator

    DEFAULT_ARGS = {
        "owner": "footballpulse",
        "retries": 2,
        "retry_delay": datetime.timedelta(minutes=1),
        "execution_timeout": datetime.timedelta(minutes=30),
    }

    @dag(
        dag_id="footballpulse_process",
        schedule="*/30 * * * *",
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,
        tags=["footballpulse", "v2", "process"],
    )
    def footballpulse_process():
        process_task = BashOperator(
            task_id="process_backlog",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_PROCESS_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --rm processor python -m footballpulse_pipeline process",
            ),
        )

        trigger_publish = TriggerDagRunOperator(
            task_id="trigger_publish_v2",
            trigger_dag_id="footballpulse_publish",
            wait_for_completion=False,
            reset_dag_run=True,
        )

        process_task >> trigger_publish

    footballpulse_process_dag = footballpulse_process()
except ImportError:
    footballpulse_process_dag = None
