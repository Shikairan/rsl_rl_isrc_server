FROM rsl_rl_isrc:v3

ENV SERVER_B_WORKSPACE_ROOT=/workspace \
    SERVER_B_LAUNCHER=torchrun \
    PYTHONPATH=/opt/serverB \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY app /opt/serverB/app
COPY entrypoint.b.sh /opt/serverB/entrypoint.sh
COPY requirements.txt /opt/serverB/requirements.txt

RUN chmod +x /opt/serverB/entrypoint.sh \
    && python3 -m pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "pydantic>=2.9.0"

WORKDIR /workspace
EXPOSE 8080
ENTRYPOINT ["/opt/serverB/entrypoint.sh"]
