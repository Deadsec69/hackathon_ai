FROM grafana/grafana:9.0.0

COPY ./provisioning /etc/grafana/provisioning

ENV GF_SECURITY_ADMIN_PASSWORD=admin
ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-simple-json-datasource

EXPOSE 3000
