"""Version 2 publisher orchestration from Mongo into Supabase PostgreSQL."""

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
        "execution_timeout": datetime.timedelta(minutes=15),
    }

    @dag(
        dag_id="footballpulse_publish",
        schedule=None,
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,
        tags=["footballpulse", "v2", "publish"],
    )
    def footballpulse_publish():
        BashOperator(
            task_id="publish_read_model",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_PUBLISH_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --no-deps --rm publisher python -m footballpulse_pipeline publish",
            ),
        )

    footballpulse_publish_dag = footballpulse_publish()
except ImportError:
    footballpulse_publish_dag = None
