FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/pkg/PredictAP_python:/app/app

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

# App source
COPY app/ ./app/

# Persistent results directory
RUN mkdir -p /app/save_tmp

# Entrypoint installs PredictAP at startup from the mounted volume
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/entrypoint.sh"]
