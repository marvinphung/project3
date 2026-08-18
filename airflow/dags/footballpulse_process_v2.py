"""Version 2 processing orchestration for the local-only pipeline."""

from __future__ import annotations

import os

try:
    import pendulum
    from airflow.decorators import dag
    from airflow.operators.bash import BashOperator

    @dag(
        dag_id="footballpulse_process",
        schedule="*/30 * * * *",
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        tags=["footballpulse", "v2", "process"],
    )
    def footballpulse_process():
        BashOperator(
            task_id="process_backlog",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_PROCESS_COMMAND", "python -m footballpulse_pipeline process"
            ),
        )

    footballpulse_process_dag = footballpulse_process()
except ImportError:
    footballpulse_process_dag = None
