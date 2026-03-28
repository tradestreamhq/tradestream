FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY *.py ./

ENV DB_HOST=localhost \
    DB_PORT=5432 \
    DB_NAME="" \
    DB_USER=postgres \
    DB_PASSWORD=""

EXPOSE 8080

ENTRYPOINT ["python", "main.py"]
CMD ["--mcp_transport", "stdio"]
