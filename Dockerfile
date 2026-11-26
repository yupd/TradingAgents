FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 可选构建源：默认官方源，国内构建时用 --build-arg 覆盖。
ARG APT_MIRROR
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST

RUN if [ -n "$APT_MIRROR" ]; then \
        sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[web]"

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /home/appuser/.tradingagents \
    && chown -R appuser:appuser /app /home/appuser/.tradingagents

# Streamlit 原生环境变量：容器内监听所有地址，关闭浏览器与遥测。
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

USER appuser
EXPOSE 8501
CMD ["tradingagents-web"]
