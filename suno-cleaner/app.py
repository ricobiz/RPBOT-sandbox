"""
Suno Cleaner - FastAPI Application
Web interface for audio processing pipeline
"""

import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

from pipeline import Pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Suno Cleaner", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job storage
jobs = {}
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def process_audio(job_id: str, audio_path: str):
    """Background task to process audio."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Обработка аудио..."
        
        pipeline = Pipeline(output_dir=str(OUTPUT_DIR))
        result = pipeline.run(audio_path)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["message"] = "Готово!"
        jobs[job_id]["result"] = result
        jobs[job_id]["output_file"] = result.get("mastered", "")
        
        pipeline.cleanup()
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = f"Ошибка: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def root():
    """Return the main HTML UI."""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Suno Cleaner - Очистка и мастеринг</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        h1 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 40px;
        }
        
        .upload-area {
            background: rgba(255, 255, 255, 0.05);
            border: 2px dashed #444;
            border-radius: 20px;
            padding: 60px 40px;
            text-align: center;
            transition: all 0.3s ease;
            cursor: pointer;
            margin-bottom: 30px;
        }
        
        .upload-area:hover {
            border-color: #00d4ff;
            background: rgba(255, 255, 255, 0.08);
        }
        
        .upload-area.dragover {
            border-color: #00d4ff;
            background: rgba(0, 212, 255, 0.1);
        }
        
        .upload-icon {
            font-size: 4rem;
            margin-bottom: 20px;
        }
        
        .upload-text {
            font-size: 1.2rem;
            margin-bottom: 10px;
        }
        
        .upload-hint {
            color: #666;
            font-size: 0.9rem;
        }
        
        #fileInput {
            display: none;
        }
        
        .btn {
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            border: none;
            color: white;
            padding: 15px 40px;
            font-size: 1.1rem;
            border-radius: 30px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin-top: 20px;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.3);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .status-area {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 30px;
            margin-top: 30px;
            display: none;
        }
        
        .status-area.visible {
            display: block;
        }
        
        .status-title {
            font-size: 1.3rem;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .spinner {
            width: 24px;
            height: 24px;
            border: 3px solid #333;
            border-top-color: #00d4ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .progress-bar {
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
            margin: 20px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            width: 0%;
            transition: width 0.3s ease;
        }
        
        .status-message {
            color: #aaa;
            font-size: 0.95rem;
        }
        
        .result-area {
            margin-top: 30px;
            padding: 20px;
            background: rgba(0, 212, 255, 0.1);
            border-radius: 10px;
            display: none;
        }
        
        .result-area.visible {
            display: block;
        }
        
        .download-btn {
            display: inline-block;
            background: #00d4ff;
            color: #1a1a2e;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
            margin-top: 15px;
            transition: transform 0.2s;
        }
        
        .download-btn:hover {
            transform: scale(1.05);
        }
        
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 50px;
        }
        
        .feature-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
        }
        
        .feature-icon {
            font-size: 2rem;
            margin-bottom: 15px;
        }
        
        .feature-title {
            font-size: 1.1rem;
            margin-bottom: 10px;
            color: #00d4ff;
        }
        
        .feature-desc {
            font-size: 0.9rem;
            color: #888;
        }
        
        footer {
            text-align: center;
            margin-top: 60px;
            color: #555;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Suno Cleaner</h1>
        <p class="subtitle">Профессиональная очистка и мастеринг аудио</p>
        
        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">🎧</div>
            <div class="upload-text">Перетащите аудиофайл сюда</div>
            <div class="upload-hint">или нажмите для выбора файла</div>
            <input type="file" id="fileInput" accept="audio/*">
            <button class="btn" id="uploadBtn">Выбрать файл</button>
        </div>
        
        <div class="status-area" id="statusArea">
            <div class="status-title">
                <div class="spinner" id="spinner"></div>
                <span>Статус обработки</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
            </div>
            <div class="status-message" id="statusMessage">Подготовка...</div>
            
            <div class="result-area" id="resultArea">
                <h3>✅ Обработка завершена!</h3>
                <p>Ваш аудиофайл готов к скачиванию:</p>
                <a href="#" class="download-btn" id="downloadBtn">Скачать обработанный файл</a>
            </div>
        </div>
        
        <div class="features">
            <div class="feature-card">
                <div class="feature-icon">🎚️</div>
                <div class="feature-title">Разделение стемов</div>
                <div class="feature-desc">Извлечение вокала, басов, ударных и других инструментов</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🎹</div>
                <div class="feature-title">MIDI экстракция</div>
                <div class="feature-desc">Извлечение мелодии и гармоний в MIDI формат</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔊</div>
                <div class="feature-title">Рендеринг VST</div>
                <div class="feature-desc">Синтез звука с использованием виртуальных инструментов</div>
            </div>
            <div class="feature-card">
                <div class="feature-icon">✨</div>
                <div class="feature-title">Мастеринг</div>
                <div class="feature-desc">Профессиональная обработка звука и нормализация</div>
            </div>
        </div>
        
        <footer>
            <p>Suno Cleaner © 2024 | Демонстрация технологий AI-обработки аудио</p>
        </footer>
    </div>
    
    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');
        const statusArea = document.getElementById('statusArea');
        const statusMessage = document.getElementById('statusMessage');
        const progressFill = document.getElementById('progressFill');
        const spinner = document.getElementById('spinner');
        const resultArea = document.getElementById('resultArea');
        const downloadBtn = document.getElementById('downloadBtn');
        
        let currentJobId = null;
        
        // Click to upload
        uploadArea.addEventListener('click', (e) => {
            if (e.target !== uploadBtn) {
                fileInput.click();
            }
        });
        
        uploadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });
        
        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                uploadFile(files[0]);
            }
        });
        
        // File selected
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
        
        async function uploadFile(file) {
            statusArea.classList.add('visible');
            resultArea.classList.remove('visible');
            statusMessage.textContent = 'Загрузка файла...';
            progressFill.style.width = '10%';
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error('Upload failed');
                }
                
                const data = await response.json();
                currentJobId = data.job_id;
                
                statusMessage.textContent = 'Ожидание обработки...';
                progressFill.style.width = '30%';
                
                // Start polling for status
                pollStatus();
                
            } catch (error) {
                statusMessage.textContent = 'Ошибка: ' + error.message;
                spinner.style.display = 'none';
            }
        }
        
        async function pollStatus() {
            if (!currentJobId) return;
            
            const interval = setInterval(async () => {
                try {
                    const response = await fetch(`/status/${currentJobId}`);
                    const data = await response.json();
                    
                    statusMessage.textContent = data.message || data.status;
                    
                    if (data.status === 'processing') {
                        progressFill.style.width = '60%';
                    } else if (data.status === 'completed') {
                        progressFill.style.width = '100%';
                        clearInterval(interval);
                        spinner.style.display = 'none';
                        
                        resultArea.classList.add('visible');
                        downloadBtn.href = `/download/${currentJobId}`;
                        
                        statusMessage.textContent = 'Готово! Файл обработан и оптимизирован.';
                    } else if (data.status === 'failed') {
                        clearInterval(interval);
                        spinner.style.display = 'none';
                        statusMessage.textContent = 'Ошибка: ' + (data.message || 'Неизвестная ошибка');
                    }
                    
                } catch (error) {
                    console.error('Status check failed:', error);
                }
            }, 2000);
        }
    </script>
</body>
</html>"""


@app.post("/process")
async def process_audio_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Process an uploaded audio file."""
    # Save uploaded file
    job_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Initialize job
    jobs[job_id] = {
        "status": "queued",
        "message": "В очереди на обработку",
        "file_path": str(file_path),
        "result": None,
        "output_file": None
    }
    
    # Start background processing
    background_tasks.add_task(process_audio, job_id, str(file_path))
    
    return {"job_id": job_id, "status": "queued", "message": "Файл загружен, начало обработки..."}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Get the status of a processing job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """Download the processed audio file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    output_file = job.get("output_file")
    if not output_file or not os.path.exists(output_file):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    return FileResponse(output_file, filename="suno_cleaned.wav", media_type="audio/wav")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "suno-cleaner"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)