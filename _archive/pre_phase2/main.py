from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import threading
import os
import uuid
from typing import Dict, Any
import uvicorn

app = FastAPI()

download_progress: Dict[str, Dict[str, Any]] = {}
os.makedirs('./downloads', exist_ok=True)

class DownloadRequest(BaseModel):
    url: str

class ExtractLinkRequest(BaseModel):
    url: str

def progress_hook(task_id):
    def hook(d):
        if d['status'] == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            percent = (downloaded / total) * 100 if total > 0 else 0.0
            download_progress[task_id] = {
                'status': 'downloading',
                'progress': percent,
                'eta': d.get('eta'),
                'speed': d.get('speed')
            }
        elif d['status'] == 'finished':
            download_progress[task_id] = {'status': 'completed', 'progress': 100.0, 'eta': None, 'speed': None}
        elif d['status'] == 'error':
            download_progress[task_id] = {'status': 'failed', 'error': str(d.get('error'))}
    return hook

def download_video(task_id: str, url: str):
    try:
        download_progress[task_id] = {'status': 'starting', 'progress': 0.0, 'eta': None, 'speed': None}
        ydl_opts = {
            'outtmpl': './downloads/%(title)s.%(ext)s',
            'progress_hooks': [progress_hook(task_id)],
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'retries': 3,
            'ignoreerrors': False
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            ydl_opts_fallback = ydl_opts.copy()
            ydl_opts_fallback['format'] = 'best'
            ydl_opts_fallback['merge_output_format'] = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                    ydl.download([url])
            except Exception as e2:
                download_progress[task_id] = {'status': 'failed', 'error': str(e2)}
    except Exception as e:
        download_progress[task_id] = {'status': 'failed', 'error': str(e)}

@app.post("/download")
async def download(request: DownloadRequest):
    task_id = str(uuid.uuid4())
    thread = threading.Thread(target=download_video, args=(task_id, request.url))
    thread.start()
    return {"task_id": task_id, "message": "Download started"}

@app.post("/extract-link")
async def extract_link(request: ExtractLinkRequest):
    try:
        ydl_opts = {
            'skip_download': True,
            'dump_single_json': True,
            'format': 'best'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            direct_urls = []
            if 'formats' in info:
                for fmt in info['formats']:
                    if 'url' in fmt:
                        direct_urls.append({
                            'format_id': fmt.get('format_id'),
                            'url': fmt['url'],
                            'ext': fmt.get('ext'),
                            'resolution': fmt.get('resolution', 'unknown')
                        })
            return {"direct_urls": direct_urls, "title": info.get('title', 'unknown')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
