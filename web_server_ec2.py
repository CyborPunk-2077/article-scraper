#!/usr/bin/env python3
"""
Ultimate Scraper V2 - Web Interface Backend (EC2 Version)
Flask server for managing scraping jobs with S3 integration
Runs directly on EC2 - no SSH needed
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration - EC2 Version (no SSH needed)
SCRAPER_PATH = "/home/ec2-user/ultimate_scraper_v2.py"
SCRAPER_ENV_PATH = "/home/ec2-user/ultimate_scraper_env/bin/activate"

# S3 Configuration
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'bockscraper')
S3_TEXT_BUCKET_NAME = 'bockscraper1'
S3_SUMMARY_BUCKET_NAME = 'bockscraper2'
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# Global state
scraping_active = False
current_job = None
all_logs = []
scraping_stats = {
    'articlesFound': 0,
    'articlesSaved': 0,
    'imagesFound': 0,
    'progress': 0,
    'completed': False,
    'sessionId': None
}

conversion_active = False
conversion_logs = []
conversion_stats = {'completed': False, 'error': None, 'targetBucket': None}

summarization_active = False
summarization_logs = []
summarization_stats = {
    'completed': False, 'error': None, 'targetBucket': S3_SUMMARY_BUCKET_NAME,
    'textSummaries': 0, 'imageSummaries': 0, 'totalFolders': 0
}

def add_log(message, log_type="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {'timestamp': timestamp, 'message': message, 'type': log_type}
    all_logs.append(log_entry)
    logger.info(f"[{log_type}] {message}")
    if len(all_logs) > 500:
        all_logs.pop(0)

def add_conversion_log(message, log_type="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {'timestamp': timestamp, 'message': message, 'type': log_type}
    conversion_logs.append(log_entry)
    logger.info(f"[CONVERT][{log_type}] {message}")
    if len(conversion_logs) > 200:
        conversion_logs.pop(0)

def add_summarization_log(message, log_type="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {'timestamp': timestamp, 'message': message, 'type': log_type}
    summarization_logs.append(log_entry)
    logger.info(f"[SUMMARIZE][{log_type}] {message}")
    if len(summarization_logs) > 300:
        summarization_logs.pop(0)

def _run_conversion(source_session):
    global conversion_active, conversion_stats
    try:
        add_conversion_log(f"Starting conversion for session: {source_session}", "info")
        
        s3 = boto3.client('s3', region_name=AWS_REGION)
        prefix = f"{source_session}/"
        
        add_conversion_log(f"Listing files in s3://{S3_BUCKET_NAME}/{prefix}", "info")
        paginator = s3.get_paginator('list_objects_v2')
        
        files_converted = 0
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('.json') and not key.endswith('_summary.json'):
                    try:
                        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                        content = response['Body'].read().decode('utf-8')
                        data = json.loads(content)
                        
                        title = data.get('title', 'No Title')
                        author = data.get('author', 'Unknown')
                        date = data.get('date', 'Unknown')
                        text_content = data.get('content', '') or data.get('text', '') or data.get('article', '')
                        
                        if text_content:
                            formatted_text = f"Title: {title}\nAuthor: {author}\nDate: {date}\n\nContent:\n{text_content}"
                            txt_key = key.replace('.json', '.txt')
                            s3.put_object(
                                Bucket=S3_TEXT_BUCKET_NAME,
                                Key=txt_key,
                                Body=formatted_text.encode('utf-8'),
                                ContentType='text/plain'
                            )
                            files_converted += 1
                            add_conversion_log(f"Converted: {key} -> {txt_key}", "success")
                        else:
                            add_conversion_log(f"Skipped {key} (no text content)", "warning")
                    except Exception as e:
                        add_conversion_log(f"Error converting {key}: {str(e)}", "error")
        
        conversion_stats['filesConverted'] = files_converted
        conversion_stats['completed'] = True
        add_conversion_log(f"Conversion complete! {files_converted} files converted to s3://{S3_TEXT_BUCKET_NAME}", "success")
        
    except Exception as e:
        conversion_stats['error'] = str(e)
        add_conversion_log(f"Conversion failed: {str(e)}", "error")
    finally:
        conversion_active = False

def _run_summarization(source_session):
    global summarization_active, summarization_stats
    try:
        add_summarization_log(f"Starting AI summarization for session: {source_session}", "info")
        
        s3 = boto3.client('s3', region_name=AWS_REGION)
        prefix = f"{source_session}/"
        
        add_summarization_log(f"Listing files in s3://{S3_BUCKET_NAME}/{prefix}", "info")
        paginator = s3.get_paginator('list_objects_v2')
        
        # Check if transformers is available
        try:
            import transformers
            from transformers import pipeline
            from PIL import Image
            import tempfile
            add_summarization_log("AI libraries loaded successfully", "info")
        except ImportError as ie:
            raise Exception(f"Missing AI libraries: {str(ie)}. Run: pip install transformers torch pillow")
        
        add_summarization_log("Loading text summarization model (distilbart)...", "info")
        text_summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6", device="cpu")
        
        add_summarization_log("Loading image captioning model (BLIP-tiny)...", "info")
        image_captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base", device="cpu")
        
        text_count = 0
        image_count = 0
        
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Process JSON files
                if key.endswith('.json') and not key.endswith('_summary.json'):
                    try:
                        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                        content = response['Body'].read().decode('utf-8')
                        data = json.loads(content)
                        text = data.get('content', '') or data.get('text', '')
                        
                        if text and len(text) > 100:
                            add_summarization_log(f"Summarizing text: {key}", "info")
                            summary = text_summarizer(text[:1024], max_length=150, min_length=40, do_sample=False)[0]['summary_text']
                            
                            summary_data = {'filename': key.split('/')[-1], 'summary_type': 'text', 'summary': summary}
                            summary_key = key.replace('.json', '_text_summary.json')
                            s3.put_object(
                                Bucket=S3_SUMMARY_BUCKET_NAME,
                                Key=summary_key,
                                Body=json.dumps(summary_data, indent=2).encode('utf-8'),
                                ContentType='application/json'
                            )
                            text_count += 1
                            add_summarization_log(f"✓ Text summary saved: {summary_key}", "success")
                    except Exception as e:
                        add_summarization_log(f"Error summarizing {key}: {str(e)}", "error")
                
                # Process images
                elif key.lower().endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        add_summarization_log(f"Captioning image: {key}", "info")
                        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                        
                        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                            tmp.write(response['Body'].read())
                            tmp_path = tmp.name
                        
                        img = Image.open(tmp_path).convert('RGB')
                        caption = image_captioner(img)[0]['generated_text']
                        os.unlink(tmp_path)
                        
                        caption_data = {'filename': key.split('/')[-1], 'summary_type': 'image', 'summary': caption}
                        caption_key = key.rsplit('.', 1)[0] + '_image_summary.json'
                        s3.put_object(
                            Bucket=S3_SUMMARY_BUCKET_NAME,
                            Key=caption_key,
                            Body=json.dumps(caption_data, indent=2).encode('utf-8'),
                            ContentType='application/json'
                        )
                        image_count += 1
                        add_summarization_log(f"✓ Image caption saved: {caption_key}", "success")
                    except Exception as e:
                        add_summarization_log(f"Error captioning {key}: {str(e)}", "error")
        
        summarization_stats['textSummaries'] = text_count
        summarization_stats['imageSummaries'] = image_count
        summarization_stats['completed'] = True
        add_summarization_log(f"Complete! {text_count} text summaries, {image_count} image captions -> s3://{S3_SUMMARY_BUCKET_NAME}", "success")
        
    except Exception as e:
        summarization_stats['error'] = str(e)
        add_summarization_log(f"Summarization failed: {str(e)}", "error")
    finally:
        summarization_active = False

class LocalScrapingJob:
    """Run scraper locally on EC2 (no SSH)"""
    def __init__(self, url, max_articles):
        self.url = url
        self.max_articles = max_articles
        self.start_time = time.time()
        self.process = None
        self.process_thread = None
        self.is_running = False
        self.session_id = f"session_{int(time.time())}"
        
    def start(self):
        self.is_running = True
        self.process_thread = threading.Thread(target=self._run_scraping)
        self.process_thread.start()
        
    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
        
    def _run_scraping(self):
        global scraping_active, scraping_stats
        
        try:
            add_log("Starting local scraper...", "info")
            scraping_stats['progress'] = 10
            
            remote_output_path = f"/home/ec2-user/scraping_output_{self.session_id}"
            
            # Build command - run locally with unbuffered output
            command = f"""
export PATH=/usr/local/bin:/usr/bin:/bin && \
source {SCRAPER_ENV_PATH} && \
mkdir -p {remote_output_path} && \
python -u {SCRAPER_PATH} "{self.url}" --max-articles {self.max_articles} --output {remote_output_path} && \
aws s3 sync {remote_output_path}/ s3://{S3_BUCKET_NAME}/{self.session_id}/ && \
rm -rf {remote_output_path}
"""
            
            add_log(f"Scraping {self.max_articles} articles from {self.url}", "info")
            add_log(f"Session ID: {self.session_id}", "info")
            scraping_stats['progress'] = 15
            scraping_stats['sessionId'] = self.session_id
            
            # Execute locally with unbuffered output
            self.process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                executable='/bin/bash',
                text=True,
                bufsize=0,
                universal_newlines=True
            )
            
            # Stream output
            for line in iter(self.process.stdout.readline, ''):
                if not self.is_running:
                    break
                line = line.strip()
                if line:
                    log_type = self._classify_log_line(line)
                    add_log(line, log_type)
                    self._update_stats_from_log(line)
            
            self.process.wait()
            
            if self.process.returncode == 0 and self.is_running:
                add_log("Scraping completed successfully!", "success")
                add_log(f"Files uploaded to S3: {S3_BUCKET_NAME}/{self.session_id}", "success")
                scraping_stats['progress'] = 100
                scraping_stats['completed'] = True
            else:
                add_log("Scraping failed or was stopped", "error")
                scraping_stats['progress'] = 0
                
        except Exception as e:
            add_log(f"Error: {str(e)}", "error")
            scraping_stats['progress'] = 0
        finally:
            self.is_running = False
            scraping_active = False
            
    def _classify_log_line(self, line):
        line_lower = line.lower()
        if any(w in line_lower for w in ['error', 'failed', 'exception']):
            return 'error'
        elif any(w in line_lower for w in ['success', 'saved', 'complete']):
            return 'success'
        elif any(w in line_lower for w in ['warning', 'filtered']):
            return 'warning'
        return 'info'
    
    def _update_stats_from_log(self, line):
        global scraping_stats
        
        # Count only when article.json is SAVED (actual articles found = articles saved)
        if "SAVED:" in line and "article.json" in line:
            scraping_stats['articlesFound'] = scraping_stats.get('articlesFound', 0) + 1
            scraping_stats['articlesSaved'] = scraping_stats['articlesFound']
            progress = min(15 + (scraping_stats['articlesFound'] / self.max_articles) * 65, 80)
            scraping_stats['progress'] = max(scraping_stats['progress'], int(progress))
            
        # Count only when image.jpg is SAVED (actual save)
        if "SUCCESS: Saved" in line and "image.jpg" in line:
            scraping_stats['imagesFound'] = scraping_stats.get('imagesFound', 0) + 1
            progress = min(80 + (scraping_stats['imagesFound'] / self.max_articles) * 15, 95)
            scraping_stats['progress'] = max(scraping_stats['progress'], int(progress))
            
        # Check for completion
        if "COMPLETE" in line.upper():
            scraping_stats['progress'] = 100

# Flask routes
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/Health Text-01.png')
def logo():
    return send_from_directory('.', 'Health Text-01.png')

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    global scraping_active, current_job, scraping_stats
    
    if scraping_active:
        return jsonify({'error': 'Scraping already in progress'}), 400
    
    data = request.json
    url = data.get('url')
    max_articles = data.get('maxArticles', 10)
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Reset stats
    scraping_stats = {
        'articlesFound': 0, 'articlesSaved': 0, 'imagesFound': 0,
        'progress': 0, 'completed': False, 'sessionId': None
    }
    all_logs.clear()
    
    scraping_active = True
    current_job = LocalScrapingJob(url, max_articles)
    current_job.start()
    
    return jsonify({
        'status': 'started',
        'sessionId': current_job.session_id,
        'message': 'Scraping job started'
    })

@app.route('/stop_scraping', methods=['POST'])
def stop_scraping():
    global scraping_active, current_job
    if current_job:
        current_job.stop()
    scraping_active = False
    return jsonify({'status': 'stopped'})

@app.route('/get_status', methods=['GET'])
def get_status():
    return jsonify({
        'active': scraping_active,
        'logs': all_logs,
        **scraping_stats
    })

@app.route('/list_bucket', methods=['POST'])
def list_bucket():
    data = request.json
    bucket = data.get('bucket')
    prefix = data.get('prefix', '')
    
    try:
        s3 = boto3.client('s3', region_name=AWS_REGION)
        
        if prefix and not prefix.endswith('/'):
            prefix += '/'
        
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter='/')
        
        folders = []
        files = []
        
        for cp in response.get('CommonPrefixes', []):
            folder_name = cp['Prefix'][len(prefix):].rstrip('/')
            folders.append({'name': folder_name})
        
        for obj in response.get('Contents', []):
            key = obj['Key']
            if key == prefix:
                continue
            file_name = key[len(prefix):]
            if '/' not in file_name:
                files.append({
                    'name': file_name,
                    'key': key,
                    'size': obj['Size'],
                    'lastModified': obj['LastModified'].isoformat()
                })
        
        return jsonify({'folders': folders, 'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_file', methods=['POST'])
def download_file():
    data = request.json
    bucket = data.get('bucket')
    key = data.get('key')
    
    try:
        s3 = boto3.client('s3', region_name=AWS_REGION)
        file_obj = s3.get_object(Bucket=bucket, Key=key)
        
        from flask import Response
        return Response(
            file_obj['Body'].read(),
            mimetype=file_obj.get('ContentType', 'application/octet-stream'),
            headers={'Content-Disposition': f'attachment; filename={key.split("/")[-1]}'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/convert_to_text', methods=['POST'])
def convert_to_text():
    global conversion_active, conversion_stats
    
    if conversion_active:
        return jsonify({'error': 'Conversion already in progress'}), 400
    
    data = request.json
    source_session = data.get('sourceSession', '')
    
    if not source_session:
        return jsonify({'error': 'sourceSession is required'}), 400
    
    conversion_logs.clear()
    conversion_stats = {'completed': False, 'error': None, 'targetBucket': S3_TEXT_BUCKET_NAME, 'filesConverted': 0}
    conversion_active = True
    
    thread = threading.Thread(target=_run_conversion, args=(source_session,))
    thread.start()
    
    return jsonify({'status': 'started', 'message': 'Conversion started', 'targetBucket': S3_TEXT_BUCKET_NAME})

@app.route('/conversion_status', methods=['GET'])
def conversion_status():
    return jsonify({'logs': conversion_logs, **conversion_stats})

@app.route('/generate_summaries', methods=['POST'])
def generate_summaries():
    global summarization_active, summarization_stats
    
    if summarization_active:
        return jsonify({'error': 'Summarization already in progress'}), 400
    
    data = request.json
    source_session = data.get('sourceSession', '')
    
    if not source_session:
        return jsonify({'error': 'sourceSession is required'}), 400
    
    summarization_logs.clear()
    summarization_stats = {
        'completed': False, 'error': None, 'targetBucket': S3_SUMMARY_BUCKET_NAME,
        'textSummaries': 0, 'imageSummaries': 0, 'totalFolders': 0
    }
    summarization_active = True
    
    thread = threading.Thread(target=_run_summarization, args=(source_session,))
    thread.start()
    
    return jsonify({'status': 'started', 'message': 'Summarization started', 'targetBucket': S3_SUMMARY_BUCKET_NAME})

@app.route('/summarization_status', methods=['GET'])
def summarization_status():
    return jsonify({'logs': summarization_logs, **summarization_stats})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
