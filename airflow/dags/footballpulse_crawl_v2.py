"""Version 2 crawl orchestration for the local-only pipeline."""

from __future__ import annotations

import os

try:
    import pendulum
    from airflow.decorators import dag
    from airflow.operators.bash import BashOperator

    @dag(
        dag_id="footballpulse_crawl",
        schedule="*/30 * * * *",
        start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
        catchup=False,
        max_active_runs=1,
        tags=["footballpulse", "v2", "crawl"],
    )
    def footballpulse_crawl():
        BashOperator(
            task_id="crawl_sources",
            bash_command=os.environ.get(
                "FOOTBALLPULSE_CRAWL_COMMAND", "python -m footballpulse_pipeline crawl"
            ),
            env={"FOOTBALLPULSE_CRAWL_MODE": "scheduled"},
        )

    footballpulse_crawl_dag = footballpulse_crawl()
except ImportError:
    footballpulse_crawl_dag = None
