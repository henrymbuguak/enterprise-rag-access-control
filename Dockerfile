FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/srv/app HF_HOME=/models
WORKDIR /srv
# CPU-only PyTorch keeps the image around 1.5 GB instead of 5 GB
RUN pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ /srv/app/
CMD ["uvicorn", "brimmora.api:app", "--host", "0.0.0.0", "--port", "8000"]
