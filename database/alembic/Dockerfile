FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir alembic==1.18.4 psycopg2-binary==2.9.10 sqlalchemy==2.0.48

COPY . /app/database/alembic/

ENTRYPOINT ["python", "-m", "database.alembic.run_migrations"]
