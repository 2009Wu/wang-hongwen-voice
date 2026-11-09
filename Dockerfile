FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg sox libsox-fmt-all libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Share the large CUDA wheels, isolate incompatible model/UI dependencies.
RUN pip install --no-cache-dir numpy==1.26.4 \
    && pip install --no-cache-dir torch==2.7.1 torchaudio==2.7.1 \
       --index-url https://download.pytorch.org/whl/cu128 \
    && python -m venv /opt/ui \
    && python -m venv --system-site-packages /opt/singing \
    && python -m venv --system-site-packages /opt/speech

COPY requirements-ui.txt requirements-singing.txt requirements-tts.txt /tmp/requirements/
RUN /opt/ui/bin/pip install --no-cache-dir -r /tmp/requirements/requirements-ui.txt \
    && /opt/singing/bin/pip install --no-cache-dir -r /tmp/requirements/requirements-singing.txt \
    && /opt/speech/bin/pip install --no-cache-dir -r /tmp/requirements/requirements-tts.txt

RUN useradd --create-home --uid 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user:user . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    MODEL_CACHE=/home/user/.cache/wang-voice \
    SING_PYTHON=/opt/singing/bin/python \
    TTS_PYTHON=/opt/speech/bin/python \
    GRADIO_ANALYTICS_ENABLED=False \
    GRADIO_TEMP_DIR=/tmp/wang-voice-gradio \
    TOKENIZERS_PARALLELISM=false \
    PORT=7860

EXPOSE 7860
CMD ["/opt/ui/bin/python", "app.py"]
