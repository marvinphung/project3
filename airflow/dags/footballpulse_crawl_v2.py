"""Version 2 crawl orchestration for the local-only pipeline."""

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
        dag_id="footballpulse_crawl",
        schedule=None,
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,
        tags=["footballpulse", "v2", "crawl"],
    )
    def footballpulse_crawl():
        BashOperator(
            task_id="crawl_sources",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_CRAWL_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --no-deps --rm crawler python -m footballpulse_pipeline crawl",
            ),
            env={"FOOTBALLPULSE_CRAWL_MODE": "scheduled"},
            append_env=True,
        )

    footballpulse_crawl_dag = footballpulse_crawl()
except ImportError:
    footballpulse_crawl_dag = None
