"""Version 2 content summary orchestration for the local-only pipeline."""

from __future__ import annotations

import datetime
import os

try:
    import pendulum
    from airflow.decorators import dag
    from airflow.operators.bash import BashOperator

    DEFAULT_ARGS = {
        "owner": "footballpulse",
        "retries": 2,
        "retry_delay": datetime.timedelta(minutes=1),
        "execution_timeout": datetime.timedelta(minutes=30),
    }

    @dag(
        dag_id="footballpulse_summary",
        schedule=None,
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,
        tags=["footballpulse", "v2", "summary"],
    )
    def footballpulse_summary():
        BashOperator(
            task_id="summarize_entity_timelines",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_SUMMARY_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --no-deps --rm content-summary python -m footballpulse_pipeline summary",
            ),
        )

    footballpulse_summary_dag = footballpulse_summary()
except ImportError:
    footballpulse_summary_dag = None
