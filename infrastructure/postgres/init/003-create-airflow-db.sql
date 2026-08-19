SELECT 'CREATE DATABASE footballpulse_airflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'footballpulse_airflow')\gexec
