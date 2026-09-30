FROM python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY sandbox.py /opt/gatewayai-worker/sandbox.py
RUN chmod 0555 /opt/gatewayai-worker/sandbox.py
USER 65532:65532
WORKDIR /workspace
ENV HOME=/tmp/home GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
    GIT_TERMINAL_PROMPT=0 GIT_ALLOW_PROTOCOL= PYTHONDONTWRITEBYTECODE=1
# Independent upper bound even if the operator broker disconnects or is killed.
ENTRYPOINT ["timeout", "--signal=KILL", "150", "python3", "-I", "/opt/gatewayai-worker/sandbox.py"]
