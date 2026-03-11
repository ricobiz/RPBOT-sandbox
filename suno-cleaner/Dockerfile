FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    fluidsynth ffmpeg curl unzip libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p soundfonts /tmp/jobs

COPY suno-cleaner/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

RUN curl -L "https://keymusician01.s3.amazonaws.com/GeneralUser_GS.zip" -o /tmp/gu.zip \
    && unzip /tmp/gu.zip -d /tmp/gu/ \
    && find /tmp/gu -name "*.sf2" -exec cp {} /app/soundfonts/GeneralUser.sf2 \; \
    && rm -rf /tmp/gu* || echo "soundfont download skipped"

COPY suno-cleaner/pipeline.py .
COPY suno-cleaner/app.py .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]