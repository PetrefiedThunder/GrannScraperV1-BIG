# GrandmaScrape Production Deployment Guide

Complete guide for deploying GrandmaScrape to production environments.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Docker Deployment](#docker-deployment)
3. [Cloud Deployment](#cloud-deployment)
4. [Configuration](#configuration)
5. [Security](#security)
6. [Monitoring](#monitoring)
7. [Scaling](#scaling)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- 2GB+ RAM
- 10GB+ disk space

### Local Development

```bash
# 1. Install dependencies
poetry install

# 2. Install Playwright browsers
playwright install chromium

# 3. Run API server
python -m scraper.api.rest_server

# 4. Open dashboard
open http://localhost:8000
```

---

## Docker Deployment

### Basic Deployment

```bash
# 1. Build image
docker-compose build

# 2. Start services
docker-compose up -d

# 3. Check logs
docker-compose logs -f

# 4. Access dashboard
open http://localhost:8000
```

### Production Docker Configuration

**docker-compose.prod.yml**:

```yaml
version: '3.8'

services:
  grandmascrape-api:
    image: grandmascrape:latest
    container_name: grandmascrape-production
    ports:
      - "8000:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - LOG_LEVEL=warning  # Production: warning or error
      - SCRAPER_MAX_CONCURRENT=100
      - SCRAPER_RATE_LIMIT=20
      - DATABASE_URL=postgresql://user:pass@db:5432/grandmascrape
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./data:/app/data
      - ./exports:/app/exports
      - ./logs:/app/logs
    restart: always
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  grandmascrape-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: grandmascrape
      POSTGRES_USER: grandmascrape
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - db-data:/var/lib/postgresql/data
    restart: always

  grandmascrape-redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-data:/data
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - grandmascrape-api
    restart: always

volumes:
  db-data:
  redis-data:
```

### Environment Variables

Create `.env` file:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/grandmascrape
DB_PASSWORD=your-secure-password

# Redis Cache
REDIS_URL=redis://localhost:6379

# Scraper Settings
SCRAPER_MAX_CONCURRENT=100
SCRAPER_RATE_LIMIT=20
SCRAPER_TIMEOUT=30
SCRAPER_USER_AGENT=GrandmaScrape/1.0

# Security
API_KEY_REQUIRED=true
API_KEYS=key1,key2,key3
ALLOWED_ORIGINS=https://yourdomain.com

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
```

---

## Cloud Deployment

### AWS Deployment

#### Option 1: ECS Fargate

```bash
# 1. Build and push Docker image
docker build -t grandmascrape:latest .
docker tag grandmascrape:latest YOUR_ECR_REPO/grandmascrape:latest
docker push YOUR_ECR_REPO/grandmascrape:latest

# 2. Create ECS task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-def.json

# 3. Create ECS service
aws ecs create-service \
  --cluster grandmascrape-cluster \
  --service-name grandmascrape-api \
  --task-definition grandmascrape:1 \
  --desired-count 2 \
  --launch-type FARGATE
```

**ecs-task-def.json**:

```json
{
  "family": "grandmascrape",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "grandmascrape-api",
      "image": "YOUR_ECR_REPO/grandmascrape:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "API_HOST", "value": "0.0.0.0"},
        {"name": "API_PORT", "value": "8000"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/grandmascrape",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Option 2: EC2 with Auto Scaling

```bash
# 1. Launch EC2 instance (t3.medium or larger)
# 2. Install Docker
sudo yum update -y
sudo yum install -y docker
sudo service docker start

# 3. Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 4. Clone and deploy
git clone https://github.com/yourorg/grandmascrape.git
cd grandmascrape
docker-compose -f docker-compose.prod.yml up -d
```

### Google Cloud Platform (GCP)

#### Cloud Run Deployment

```bash
# 1. Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/grandmascrape

# 2. Deploy to Cloud Run
gcloud run deploy grandmascrape \
  --image gcr.io/PROJECT_ID/grandmascrape \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --max-instances 10
```

### Azure Deployment

#### Azure Container Instances

```bash
# 1. Create resource group
az group create --name grandmascrape-rg --location eastus

# 2. Create container registry
az acr create --resource-group grandmascrape-rg \
  --name grandmascrapeacr --sku Basic

# 3. Build and push
az acr build --registry grandmascrapeacr \
  --image grandmascrape:latest .

# 4. Deploy container
az container create \
  --resource-group grandmascrape-rg \
  --name grandmascrape-api \
  --image grandmascrapeacr.azurecr.io/grandmascrape:latest \
  --dns-name-label grandmascrape \
  --ports 8000 \
  --cpu 2 \
  --memory 4
```

---

## Configuration

### Nginx Reverse Proxy

**nginx.conf**:

```nginx
upstream grandmascrape_api {
    server grandmascrape-api:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req zone=api_limit burst=20 nodelay;

    # API Proxy
    location /api/ {
        proxy_pass http://grandmascrape_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Dashboard
    location / {
        proxy_pass http://grandmascrape_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Security

### API Key Authentication

Enable API key authentication in production:

```python
# In rest_server.py, add middleware:

from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        api_key = request.headers.get("Authorization")
        if not api_key or api_key not in VALID_API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return await call_next(request)
```

### Rate Limiting

```python
# Add rate limiting with slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/v1/jobs")
@limiter.limit("10/minute")
async def create_job(request: Request, ...):
    ...
```

### HTTPS/SSL

1. **Get SSL Certificate**:
   ```bash
   # Using Let's Encrypt
   certbot certonly --standalone -d yourdomain.com
   ```

2. **Configure in Nginx** (see above)

### Firewall Rules

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/api/v1/health

# Docker health
docker-compose ps
```

### Logging

**Setup centralized logging**:

```yaml
# docker-compose.prod.yml
services:
  grandmascrape-api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**View logs**:

```bash
# Docker logs
docker-compose logs -f grandmascrape-api

# Application logs
tail -f /app/logs/app.log
```

### Metrics

**Prometheus Integration** (optional):

```python
# Add prometheus client
from prometheus_client import Counter, Histogram

scrape_requests = Counter('scrape_requests_total', 'Total scrape requests')
scrape_duration = Histogram('scrape_duration_seconds', 'Scrape duration')

@app.middleware("http")
async def track_metrics(request: Request, call_next):
    scrape_requests.inc()
    with scrape_duration.time():
        response = await call_next(request)
    return response
```

---

## Scaling

### Horizontal Scaling

1. **Load Balancer Setup**:
   ```nginx
   upstream grandmascrape_cluster {
       server api1:8000;
       server api2:8000;
       server api3:8000;
   }
   ```

2. **Shared Database**: Use PostgreSQL or MySQL instead of SQLite

3. **Shared Cache**: Use Redis for distributed caching

### Vertical Scaling

```yaml
# Increase resources
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 16G
```

### Auto-Scaling (AWS)

```bash
# ECS Auto Scaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/grandmascrape-cluster/grandmascrape-api \
  --min-capacity 2 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/grandmascrape-cluster/grandmascrape-api \
  --policy-name cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration \
    '{"TargetValue":75,"PredefinedMetricSpecification":{"PredefinedMetricType":"ECSServiceAverageCPUUtilization"}}'
```

---

## Troubleshooting

### Common Issues

**Issue**: Container fails to start
```bash
# Check logs
docker-compose logs grandmascrape-api

# Check resources
docker stats

# Restart
docker-compose restart grandmascrape-api
```

**Issue**: Out of memory
```bash
# Increase memory limit in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G
```

**Issue**: Slow scraping performance
```bash
# Increase concurrent workers
SCRAPER_MAX_CONCURRENT=200

# Enable concurrent scraping
curl -X POST "http://localhost:8000/api/v1/jobs/JOB_ID/run?concurrent=true"
```

**Issue**: Database connection errors
```bash
# Check database status
docker-compose ps grandmascrape-db

# Test connection
docker-compose exec grandmascrape-api python -c \
  "import psycopg2; psycopg2.connect('$DATABASE_URL')"
```

### Performance Optimization

1. **Enable Redis caching**:
   ```python
   CACHE_ENABLED=true
   REDIS_URL=redis://redis:6379
   ```

2. **Use concurrent scraping**:
   ```python
   client.run_job(job_id, concurrent=True)
   ```

3. **Enable incremental scraping**:
   ```python
   client.run_job(job_id, incremental=True)
   ```

---

## Backup & Recovery

### Database Backup

```bash
# PostgreSQL backup
docker-compose exec grandmascrape-db pg_dump -U grandmascrape grandmascrape > backup.sql

# Restore
docker-compose exec -T grandmascrape-db psql -U grandmascrape grandmascrape < backup.sql
```

### Data Export Backup

```bash
# Backup exports directory
tar -czf exports-backup-$(date +%Y%m%d).tar.gz exports/

# Upload to S3 (AWS)
aws s3 cp exports-backup-*.tar.gz s3://your-backup-bucket/
```

---

## Support

- **Documentation**: See README.md and ULTRA_POWER.md
- **Issues**: Report at GitHub Issues
- **API Docs**: http://localhost:8000/docs

---

## License

See LICENSE file for details.
