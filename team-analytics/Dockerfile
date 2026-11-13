# Team Analytics service image: the stock CVAT server image with the service code and its SQL
# copied in. The service uses only what that image already has (Python, clickhouse_connect,
# requests); nothing is installed. Built by build-team-analytics-service.sh with
# team-analytics/service as the context.
ARG BASE_IMAGE=cvat/server:v2.82.0
FROM ${BASE_IMAGE}

# sql.py finds the SQL beside the package (team_analytics/../sql)
COPY --chown=django:django team_analytics /opt/team-analytics/team_analytics
COPY --chown=django:django sql /opt/team-analytics/sql

USER django
WORKDIR /opt/team-analytics
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# replaces the stock backend_entrypoint.sh: no migrations, no supervisord
ENTRYPOINT ["/opt/venv/bin/python", "-B", "-m", "team_analytics"]
CMD []
EXPOSE 8000
