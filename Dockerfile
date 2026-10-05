FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/app

WORKDIR /app

# System dependencies (for pyarrow / pandas builds + plink2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        wget \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Install plink2
RUN cd /tmp && wget -q https://s3.amazonaws.com/plink2-assets/alpha5/plink2_linux_x86_64_20240105.zip && \
    unzip -q plink2_linux_x86_64_20240105.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/plink2 && \
    rm plink2_linux_x86_64_20240105.zip

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PredictMP package (wheel built from PredictMP/code/PredictMP_pkg, see README)
COPY wheels/ /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/predictmp-*.whl && rm -rf /tmp/wheels

# App source
COPY app/ ./app/

# Per-session upload/result folders (Docker volume predictmp_geneexprpredict-web_session_results); writable by the non-root user
RUN mkdir -p /app/session_results && chmod 1777 /app/session_results

# Entrypoint checks PredictMP and starts Streamlit
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/entrypoint.sh"]
