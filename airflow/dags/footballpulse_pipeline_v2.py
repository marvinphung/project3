"""Master Airflow DAG for the FootballPulse v2 pipeline."""

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
    }

    def _command(env_name: str, default_command: str) -> str:
        return os.environ.get(env_name, default_command)

    @dag(
        dag_id="footballpulse_pipeline",
        schedule=os.environ.get("FOOTBALLPULSE_V2_PIPELINE_SCHEDULE", "5,35 * * * *"),
        start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,
        tags=["footballpulse", "v2", "pipeline"],
    )
    def footballpulse_pipeline():
        crawl = BashOperator(
            task_id="crawl",
            bash_command=_command(
                "FOOTBALLPULSE_PIPELINE_CRAWL_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --rm crawler python -m footballpulse_pipeline crawl",
            ),
            execution_timeout=datetime.timedelta(minutes=30),
            env={"FOOTBALLPULSE_CRAWL_MODE": "scheduled"},
            append_env=True,
        )

        entities_extraction = BashOperator(
            task_id="entities_extraction",
            bash_command=_command(
                "FOOTBALLPULSE_PIPELINE_ENTITIES_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --rm entities-extraction python -m footballpulse_pipeline process",
            ),
            execution_timeout=datetime.timedelta(minutes=45),
        )

        content_summary = BashOperator(
            task_id="content_summary",
            bash_command=_command(
                "FOOTBALLPULSE_PIPELINE_SUMMARY_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --rm content-summary python -m footballpulse_pipeline summary",
            ),
            execution_timeout=datetime.timedelta(hours=2),
        )

        publish = BashOperator(
            task_id="publish",
            bash_command=_command(
                "FOOTBALLPULSE_PIPELINE_PUBLISH_COMMAND",
                "docker compose -f /workspace/docker-compose.v2.yml run --rm publisher python -m footballpulse_pipeline publish",
            ),
            execution_timeout=datetime.timedelta(minutes=30),
        )

        crawl >> entities_extraction >> content_summary >> publish

    footballpulse_pipeline_dag = footballpulse_pipeline()
except ImportError:
    footballpulse_pipeline_dag = None
