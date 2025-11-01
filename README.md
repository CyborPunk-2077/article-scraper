# Article Scraper - AWS Web Scraping & AI Processing Platform

A comprehensive web scraping and AI-powered content processing system deployed on AWS EC2 with S3 storage integration. This platform scrapes articles from news websites, extracts images, converts content to text, and generates AI summaries.

## 🚀 Features

- **Web Scraping**: Automated article and image extraction from news websites
- **S3 Integration**: Seamless storage and retrieval from AWS S3 buckets
- **Text Conversion**: Convert JSON articles to plain text format
- **AI Summarization**: Generate summaries for text and captions for images using transformer models
- **Web Interface**: User-friendly control panel for managing all operations
- **Real-time Monitoring**: Live logs and progress tracking

## 📋 System Architecture

```
┌─────────────────┐
│  Web Interface  │ (Flask + HTML/CSS/JS)
│   (Port 5000)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Flask Backend  │◄────►│  EC2 Server  │
│ web_server_ec2  │      │              │
└────────┬────────┘      └──────────────┘
         │
         ├──► Scraper Engine (ultimate_scraper_v2.py)
         │    └─► Scrapy + Trafilatura + BeautifulSoup
         │
         ├──► S3 Buckets
         │    ├─► bockscraper (articles + images)
         │    ├─► bockscraper1 (text files)
         │    └─► bockscraper2 (AI summaries)
         │
         └──► AI Summarizer (transformers)
              ├─► BART (text summarization)
              └─► BLIP (image captioning)
```

## 🗂️ Project Structure

```
aws/
├── web_server_ec2.py          # Flask backend server
├── index.html                 # Web interface UI
├── ultimate_scraper_v2.py     # Main scraping engine
├── bock-scraper.service       # Systemd service configuration
├── requirements_web.txt       # Web server dependencies
├── requirements_scraper.txt   # Scraper dependencies
├── DEPLOYMENT_INFO.txt        # Deployment details
├── Health Text-01.png         # Logo
└── summary/                   # AI summarization module
    └── bocksummarizer-main/
        ├── summarize_all.py   # Text + image summarization
        ├── summarize_text.py  # Text-only summarization
        └── requirements.txt   # AI dependencies
```

## 🛠️ Technologies Used

### Backend
- **Python 3.x**: Core programming language
- **Flask**: Web framework
- **Gunicorn**: WSGI HTTP server
- **Boto3**: AWS SDK for Python

### Scraping
- **Scrapy**: Web crawling framework
- **Trafilatura**: Content extraction
- **Newspaper3k**: Article parsing
- **BeautifulSoup4**: HTML parsing
- **Pillow**: Image processing

### AI/ML
- **Transformers**: Hugging Face library
- **PyTorch**: Deep learning framework
- **BART**: Text summarization model
- **BLIP**: Image captioning model

### Infrastructure
- **AWS EC2**: Compute instance
- **AWS S3**: Object storage
- **Systemd**: Service management

## 📦 Installation

### Prerequisites
- AWS EC2 instance (Amazon Linux 2 or Ubuntu)
- Python 3.7+
- AWS credentials with S3 access
- 8GB+ RAM recommended for AI models

### Step 1: Clone Repository
```bash
cd /home/ec2-user
git clone <repository-url>
cd aws
```

### Step 2: Create Virtual Environments

**Web Server Environment:**
```bash
python3 -m venv web_venv
source web_venv/bin/activate
pip install -r requirements_web.txt
deactivate
```

**Scraper Environment:**
```bash
python3 -m venv ultimate_scraper_env
source ultimate_scraper_env/bin/activate
pip install -r requirements_scraper.txt
deactivate
```

### Step 3: Configure AWS Credentials
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter default region (e.g., us-east-1)
```

### Step 4: Setup Systemd Service
```bash
sudo cp bock-scraper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bock-scraper
sudo systemctl start bock-scraper
```

### Step 5: Configure Security Group
Open port 5000 in your EC2 security group:
- Type: Custom TCP
- Port: 5000
- Source: 0.0.0.0/0 (or your IP)

## 🚀 Usage

### Access Web Interface
```
http://<your-ec2-ip>:5000
```

### Tab 1: Scrape Articles
1. Enter website URL (e.g., `https://www.bbc.com/news`)
2. Set number of articles to scrape
3. Click "Start Scraping"
4. Monitor progress in real-time
5. Files saved to S3: `bockscraper/<session_id>/`

### Tab 2: Convert to Text
1. Enter session ID from scraping
2. Click "Convert to Text"
3. Text files saved to S3: `bockscraper1/<session_id>/`

### Tab 3: AI Summarization
1. Enter session ID from scraping
2. Click "Generate AI Summaries"
3. Summaries saved to S3: `bockscraper2/<session_id>/`

### View S3 Buckets
- Click "📁 View Bucket" in header
- Browse folders and files
- Download files directly

## 🔧 Configuration

### Environment Variables
```bash
export S3_BUCKET_NAME="bockscraper"
export AWS_DEFAULT_REGION="us-east-1"
export PORT=5000
```

### Scraper Settings
Edit `ultimate_scraper_v2.py`:
```python
max_articles = 40              # Maximum articles to scrape
max_concurrent = 30            # Concurrent operations
min_image_size = (100, 100)   # Minimum image dimensions
max_file_size_mb = 10         # Maximum image file size
```

### AI Models
Default models in `web_server_ec2.py`:
- Text: `sshleifer/distilbart-cnn-6-6`
- Image: `Salesforce/blip-image-captioning-base`

## 📊 Output Format

### Scraped Articles
```
bockscraper/<session_id>/<article_folder>/
├── article.json    # Article metadata and content
└── image.jpg       # Featured image
```

### Text Files
```
bockscraper1/<session_id>/<article_folder>/
└── article.txt     # Plain text format
```

### AI Summaries
```
bockscraper2/<session_id>/<article_folder>/
├── article_text_summary.json   # Text summary
└── image_summary.json          # Image caption
```

## 🔍 Scraping Features

### Article Detection
- URL pattern analysis (date patterns, article indicators)
- Content quality validation (word count, structure)
- Category page filtering
- Duplicate detection

### Image Extraction
- Multi-source approach: Trafilatura → Newspaper3k → BeautifulSoup
- OpenGraph and Twitter Card metadata
- Image quality scoring
- Size and format validation
- Automatic JPG conversion

### Content Extraction
- Trafilatura for clean text extraction
- Metadata extraction (title, author, date)
- HTML cleaning and normalization

## 🤖 AI Summarization

### Text Summarization
- Model: BART (facebook/bart-large-cnn)
- Chunking for long articles
- Fallback strategies for errors
- Configurable summary length

### Image Captioning
- Model: BLIP (Salesforce/blip-image-captioning-base)
- RGB conversion for compatibility
- Temporary file handling
- Error recovery

## 🛡️ Security Best Practices

1. **AWS Credentials**: Use IAM roles instead of hardcoded keys
2. **Security Groups**: Restrict port 5000 to specific IPs
3. **S3 Bucket Policies**: Configure appropriate access controls
4. **HTTPS**: Use reverse proxy (nginx) with SSL certificate
5. **Environment Variables**: Store sensitive data in environment

## 📝 Service Management

### Check Status
```bash
sudo systemctl status bock-scraper
```

### View Logs
```bash
sudo journalctl -u bock-scraper -f
tail -f ultimate_scraper_v2.log
```

### Restart Service
```bash
sudo systemctl restart bock-scraper
```

### Stop Service
```bash
sudo systemctl stop bock-scraper
```

## 🐛 Troubleshooting

### Scraping Issues
- **No articles found**: Check URL patterns and filters
- **Images not downloading**: Verify image URLs and size limits
- **Slow performance**: Reduce concurrent operations

### S3 Issues
- **Access Denied**: Check AWS credentials and bucket permissions
- **Upload failures**: Verify bucket names and region settings

### AI Issues
- **Out of memory**: Use smaller models or increase EC2 instance size
- **Model download fails**: Check internet connection and disk space
- **CUDA errors**: Models configured to use CPU by default

### Service Issues
- **Port already in use**: Check for other processes on port 5000
- **Service won't start**: Check logs with `journalctl -u bock-scraper`

## 📈 Performance Optimization

1. **Concurrent Operations**: Adjust `max_concurrent` based on server capacity
2. **Caching**: Enable caching for repeated scraping jobs
3. **Model Loading**: Models loaded once and reused
4. **Batch Processing**: Process multiple files in parallel
5. **Resource Limits**: Configure systemd service limits

## 🔄 Backup & Recovery

### Backup Files
```bash
# Backup configuration
tar -czf bock-backup-$(date +%Y%m%d).tar.gz \
  web_server_ec2.py \
  index.html \
  ultimate_scraper_v2.py \
  requirements_*.txt \
  bock-scraper.service
```

### Restore on New Instance
1. Upload backup files to new EC2
2. Extract: `tar -xzf bock-backup-*.tar.gz`
3. Follow installation steps
4. Restore S3 data if needed

## 📚 API Endpoints

### Scraping
- `POST /start_scraping` - Start scraping job
- `POST /stop_scraping` - Stop current job
- `GET /get_status` - Get scraping status

### Conversion
- `POST /convert_to_text` - Convert JSON to text
- `GET /conversion_status` - Get conversion status

### Summarization
- `POST /generate_summaries` - Generate AI summaries
- `GET /summarization_status` - Get summarization status

### S3 Browser
- `POST /list_bucket` - List bucket contents
- `POST /download_file` - Download file from S3

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create pull request

## 📄 License

This project is proprietary software developed for BOCK internship.

## 👥 Authors

- **Development Team**: BOCK Internship Program
- **Deployment**: AWS EC2 Infrastructure

## 📞 Support

For issues or questions:
1. Check troubleshooting section
2. Review logs: `ultimate_scraper_v2.log`
3. Contact development team

## 🎯 Future Enhancements

- [ ] Multi-language support
- [ ] Advanced filtering options
- [ ] Scheduled scraping jobs
- [ ] Email notifications
- [ ] Database integration
- [ ] API authentication
- [ ] Docker containerization
- [ ] Kubernetes deployment

## 📊 System Requirements

### Minimum
- 2 vCPUs
- 4GB RAM
- 20GB storage
- Network bandwidth: 1 Mbps

### Recommended
- 4 vCPUs
- 8GB RAM
- 50GB storage
- Network bandwidth: 10 Mbps

## 🔗 Related Documentation

- [AWS EC2 Documentation](https://docs.aws.amazon.com/ec2/)
- [AWS S3 Documentation](https://docs.aws.amazon.com/s3/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Scrapy Documentation](https://docs.scrapy.org/)
- [Transformers Documentation](https://huggingface.co/docs/transformers/)

---


