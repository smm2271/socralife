FROM pgvector/pgvector:0.8.6-pg16-trixie@sha256:c8483555ce48101872f888c1df8a895ff689d6c7c7a5f7ac266475f9dfe89e0b
RUN apt-get update && apt-get install -y --no-install-recommends restic ca-certificates && rm -rf /var/lib/apt/lists/*
COPY infra/ops/ /ops/
ENTRYPOINT ["/bin/sh"]
CMD ["/ops/backup.sh"]
