# SmartMart Analytics — Production Deployment Guide

This guide provides step-by-step instructions for deploying **SmartMart Analytics** to production environments across different hosting architectures.

---

## Deployment Architecture Options

| Method | Target Platform | Complexity | Best For |
|---|---|---|---|
| **Option 1: Docker Compose** | Any Linux/macOS/Windows with Docker | Low (One Command) | Local server, VPS, self-hosted environments |
| **Option 2: Cloud PaaS (Render / Railway)** | Render, Railway, Heroku | Low | Cloud hosting with managed database |
| **Option 3: Google Cloud Run** | GCP Cloud Run + Cloud SQL | Medium | Scalable serverless enterprise deployment |
| **Option 4: Linux VPS (Nginx + Gunicorn)** | Ubuntu / Debian / CentOS VPS | Medium | Dedicated virtual machines (AWS EC2, DigitalOcean) |
| **Option 5: Windows Server (Waitress)** | Windows Server 2019/2022 | Low | On-premise institutional Windows servers |

---

## Option 1: Docker & Docker Compose (Recommended)

Docker Compose automatically spins up and links two containers:
1. `smartmart_web`: The Flask application running under **Gunicorn WSGI** (workers: 2, threads: 4).
2. `smartmart_mysql`: **MySQL 8.0 Server** with persistent storage volume and automatic schema initialization.

### Prerequisites:
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine + Docker Compose installed.

### Step 1: Clone and Configure Environment
```bash
git clone <your-repo-url>
cd DWDMProject
```

Create a `.env` file from the template:
```bash
cp .env.production.example .env
```
Edit `.env` to define your strong database password and secret key:
```ini
DB_PASSWORD=YourStrongDatabasePassword2026!
SECRET_KEY=generate-a-strong-random-hex-string
```

### Step 2: Build and Run Containers
```bash
docker compose up --build -d
```

### Step 3: Verify Running Services
```bash
docker compose ps
```
The application will be accessible at:
👉 **`http://localhost:5000`**

### Step 4: Populate Data Warehouse (One-Time Execution)
To run the initial ETL load inside the container:
```bash
docker compose exec web python etl/pipeline.py
```

### Stop Services:
```bash
docker compose down
```
*(Data in MySQL and uploaded files are preserved in Docker named volumes).*

---

## Option 2: Cloud PaaS (Render / Railway / Heroku)

SmartMart Analytics is natively configured for cloud PaaS deployment via `Procfile` and `requirements.txt`.

### Deploying on Render:
1. Create a free account at [render.com](https://render.com).
2. **Create a MySQL Database**:
   - Go to **New** -> **PostgreSQL / MySQL** (or deploy a Managed MySQL service on Railway or Aiven).
   - Copy the provided `Internal Database URL` (e.g., `mysql://user:pass@host:port/dbname`).
3. **Create a Web Service**:
   - Connect your GitHub repository.
   - **Environment:** `Python 3`.
   - **Build Command:** `pip install -r requirements.txt`.
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 wsgi:app`.
4. **Environment Variables**:
   In the Render Dashboard under **Environment**, add:
   - `DATABASE_URL`: Your MySQL connection URL.
   - `SECRET_KEY`: Long random string.
   - `FLASK_ENV`: `production`.
   - `FLASK_DEBUG`: `0`.
5. Click **Deploy**. Render will build and deploy the web app.

---

## Option 3: Google Cloud Run (Serverless Container)

### Prerequisites:
- Google Cloud SDK (`gcloud`) installed and authenticated.
- A Google Cloud SQL (MySQL 8.0) instance.

### Step 1: Build and Push Container Image to Artifact Registry
```bash
# Configure Docker with Google Cloud
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build image
docker build -t us-central1-docker.pkg.dev/<PROJECT_ID>/smartmart-repo/smartmart-app:latest .

# Push image
docker push us-central1-docker.pkg.dev/<PROJECT_ID>/smartmart-repo/smartmart-app:latest
```

### Step 2: Deploy to Cloud Run
```bash
gcloud run deploy smartmart-analytics \
    --image us-central1-docker.pkg.dev/<PROJECT_ID>/smartmart-repo/smartmart-app:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="FLASK_ENV=production,DB_HOST=10.x.x.x,DB_USER=root,DB_PASSWORD=secret,DB_NAME=smartmart_dw" \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300
```

---

## Option 4: Linux VPS (Ubuntu / Debian with Nginx + Gunicorn + Systemd)

For a dedicated Linux VPS (AWS EC2, DigitalOcean Droplet, Linode):

### Step 1: Install System Dependencies
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv mysql-server nginx
```

### Step 2: Setup Database in MySQL
```bash
sudo mysql -e "CREATE DATABASE smartmart_dw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER 'smartmart_user'@'localhost' IDENTIFIED BY 'StrongPassword123!';"
sudo mysql -e "GRANT ALL PRIVILEGES ON smartmart_dw.* TO 'smartmart_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# Apply Star Schema
mysql -u smartmart_user -p smartmart_dw < database/schema.sql
```

### Step 3: Setup Virtual Environment & Code
```bash
cd /var/www
sudo git clone <repo_url> smartmart
cd smartmart
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.production.example .env
nano .env  # set DB credentials and SECRET_KEY
```

### Step 4: Configure Systemd Service
Create `/etc/systemd/system/smartmart.service`:
```ini
[Unit]
Description=SmartMart Analytics Gunicorn Application
After=network.target mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/smartmart
Environment="PATH=/var/www/smartmart/venv/bin"
EnvironmentFile=/var/www/smartmart/.env
ExecStart=/var/www/smartmart/venv/bin/gunicorn --workers 3 --threads 2 --bind 127.0.0.1:5000 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start smartmart
sudo systemctl enable smartmart
```

### Step 5: Configure Nginx Reverse Proxy
Create `/etc/nginx/sites-available/smartmart`:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 35M;

    location /static/ {
        alias /var/www/smartmart/static/;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 180s;
    }
}
```

Enable site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/smartmart /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

*(Optional: Install free SSL via Certbot: `sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx -d yourdomain.com`).*

---

## Option 5: Windows Server (Waitress WSGI)

For production deployment on Windows Server without Docker:

### Step 1: Open PowerShell as Administrator
```powershell
cd C:\Projects\DWDMProject
```

### Step 2: Configure Production Environment Variables
Edit `.env` to set:
```ini
FLASK_ENV=production
FLASK_DEBUG=0
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=YourLocalMySQLPassword
DB_NAME=smartmart_dw
```

### Step 3: Run the Multi-Threaded Waitress WSGI Server
```powershell
python waitress_server.py
```
*Waitress will bind to `0.0.0.0:5000` with 6 worker threads, serving production traffic reliably.*

*(To run continuously as a Windows Service in the background, use [NSSM](https://nssm.cc/) pointing to `python.exe waitress_server.py`).*

---

## Pre-Deployment Verification Checklist

Before opening the application to external users, verify:
- [x] **Database Connectivity:** Health check returns HTTP 200 at `/health`.
- [x] **Schema Integrity:** All 5 Star Schema tables (`Fact_Sales`, `Dim_Product`, `Dim_Customer`, `Dim_Date`, `Dim_Country`) exist in MySQL.
- [x] **Guest Member Seed:** `Dim_Customer` contains `Customer_ID = 1` (`UNKNOWN`).
- [x] **File Upload Limits:** Configured to `32 MB` max upload limit (`MAX_CONTENT_LENGTH`).
- [x] **WSGI Multi-Threading:** Server runs on Gunicorn (Linux/Containers) or Waitress (Windows).
- [x] **Automated Tests:** All 60 automated tests pass (`pytest -v`).
- [x] **Security:** `DEBUG = False`, `SECRET_KEY` is randomized, `SESSION_COOKIE_HTTPONLY = True`.
