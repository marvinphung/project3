"""Version 2 publisher orchestration from Mongo into Supabase PostgreSQL."""

from __future__ import annotations

import os

try:
    import pendulum
    from airflow.decorators import dag
    from airflow.operators.bash import BashOperator

    @dag(
        dag_id="footballpulse_publish",
        schedule="*/15 * * * *",
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        tags=["footballpulse", "v2", "publish"],
    )
    def footballpulse_publish():
        BashOperator(
            task_id="publish_read_model",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_PUBLISH_COMMAND", "python -m footballpulse_pipeline publish"
            ),
        )

    footballpulse_publish_dag = footballpulse_publish()
except ImportError:
    footballpulse_publish_dag = None
