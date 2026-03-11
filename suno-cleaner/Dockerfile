FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    fluidsynth \
    ffmpeg \
    libsndfile1 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create directories
RUN mkdir -p /app/output /app/uploads

# Download GeneralUser.sf2 soundfont
RUN wget -q https://github.com/frescobaldi/frescobaldi/raw/master/frescobaldi_app/resources/soundfonts/GeneralUser.sf2 -O /app/GeneralUser.sf2 || \
    wget -q https://download.sf2midi.org/download/GeneralUser%20GS%20v1.471.sf2 -O /app/GeneralUser.sf2 || \
    echo "Soundfont download skipped"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY pipeline.py .
COPY app.py .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "app.py"]