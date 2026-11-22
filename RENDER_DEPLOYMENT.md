# Deploying SmartMart Analytics on Render

This guide provides step-by-step instructions to deploy **SmartMart Analytics** to **Render** ([render.com](https://render.com)).

---

## 🏗️ Architecture on Render

```text
[ Free Cloud MySQL ] (Aiven / TiDB / Railway / Clever Cloud)
        │
        │ DATABASE_URL (SSL/TLS encrypted connection)
        ▼
[ Render Web Service ]
   ├── Python 3.10 Runtime
   ├── Build: pip install -r requirements.txt
   ├── Pre-deploy: python database/init_db.py (auto-creates Star Schema & seeds data)
   └── Start: gunicorn wsgi:app
```

> **Why a separate MySQL database?**  
> Render natively offers PostgreSQL and Redis, but not managed MySQL. Because SmartMart Analytics uses a **MySQL 8.0 Star Schema**, we connect Render to a free cloud-hosted MySQL database.

---

## Step 1: Create a Free Cloud MySQL Database (2 Minutes)

Choose any of the popular free MySQL providers below:

### Option A: Aiven for MySQL (Recommended - Free Tier)
1. Go to [aiven.io](https://aiven.io/) and create a free account.
2. Click **Create Service** -> Select **MySQL**.
3. Choose the **Free Plan** and select your closest cloud region.
4. Click **Create Service**.
5. Once running, copy the **Service URI** from the Overview tab. It looks like:
   ```text
   mysql://avnadmin:your_password@mysql-xxxxx.aivencloud.com:12345/defaultdb?ssl-mode=REQUIRED
   ```
6. In Aiven's **Databases** tab, you can create a database named `smartmart_dw` (or just use `defaultdb`).

*(Alternative free MySQL providers: [TiDB Cloud Serverless](https://tidbcloud.com/), [Railway](https://railway.app/), or [Clever Cloud](https://www.clever-cloud.com/)).*

---

## Step 2: Push Your Project to GitHub

If you haven't already initialized Git in this directory:

```powershell
cd c:\Projects\DWDMProject

# Initialize git repository
git init

# Add all files (secrets in .env are safely ignored by .gitignore)
git add .

# Commit
git commit -m "Production release ready for Render deployment"

# Link to your GitHub repository and push
git remote add origin https://github.com/<your-username>/smartmart-analytics.git
git branch -M main
git push -u origin main
```

---

## Step 3: Deploy to Render

You can deploy using either **Method 1 (Render Blueprint - Easiest)** or **Method 2 (Manual Setup)**.

### Method 1: Using the Render Blueprint (`render.yaml`) — Recommended

Our repository already includes `render.yaml` configured with all build and start commands!

1. Go to [dashboard.render.com](https://dashboard.render.com/).
2. Click **New +** -> Select **Blueprint**.
3. Connect your GitHub repository (`smartmart-analytics`).
4. Render will read `render.yaml` automatically and display the `smartmart-analytics` web service.
5. In the configuration screen:
   - For **`DATABASE_URL`**: Paste your MySQL connection URI from Step 1.
   - For **`SECRET_KEY`**: Render automatically generates a secure random value.
6. Click **Apply**.
7. Render will build dependencies, run `database/init_db.py` to create the Star Schema, and boot Gunicorn.

---

### Method 2: Manual Web Service Setup

If you prefer to configure the service manually on Render:

1. In the Render Dashboard, click **New +** -> **Web Service**.
2. Select your GitHub repository.
3. Configure the following settings:
   - **Name:** `smartmart-analytics`
   - **Region:** Choose the region closest to your MySQL database
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:**
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```bash
     python database/init_db.py && gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 180 wsgi:app
     ```
   - **Instance Type:** `Free`

4. Scroll down to **Environment Variables** and add:
   | Key | Value | Notes |
   |---|---|---|
   | `DATABASE_URL` | `mysql+pymysql://user:pass@host:port/dbname` | From Step 1 |
   | `SECRET_KEY` | *(Click "Generate" or paste a random string)* | Session security |
   | `FLASK_ENV` | `production` | Production mode |
   | `FLASK_DEBUG` | `0` | Disables debug mode |
   | `PYTHON_VERSION` | `3.10.12` | Python version |

5. Click **Create Web Service**.

---

## Step 4: Verification & Live Access

1. **Watch Deployment Logs:**
   In the Render dashboard, click on the **Logs** tab. You will see:
   ```text
   [*] Ensuring database exists...
   [*] Reading schema file from: database/schema.sql
   [*] Executing 14 SQL statements...
   [OK] Schema successfully applied!
   [OK] Seeded Unknown customer (ID=1, Code='UNKNOWN') verified.
   [SUCCESS] All 5 Star Schema tables verified successfully:
     1. Dim_Product
     2. Dim_Customer (with UNKNOWN seed)
     3. Dim_Date
     4. Dim_Country
     5. Fact_Sales (with Foreign Keys & Indexes)
   [*] Fact_Sales is empty. Performing initial ETL load of sample invoices...
   [OK] Initial sample data loaded: 20,711 rows.
   [INFO] Starting gunicorn 26.0.0
   [INFO] Listening at: http://0.0.0.0:10000
   ```

2. **Open Your Live Application:**
   Render will provide your public URL (e.g., `https://smartmart-analytics.onrender.com`).
   - Open it in your browser.
   - The Executive Dashboard will immediately display live revenue KPIs, monthly trend charts, top products, and customer segments!
   - You can test OLAP slicing/dicing, Apriori market basket mining, K-Means clustering, and decision tree classification directly in production.

---

## 💡 Render Free Tier Tips

- **Spin-down on idle:** Render's free tier spins down web services after 15 minutes of inactivity. When someone visits the site after spin-down, the first request may take ~30-50 seconds to wake up the service. Subsequent requests will be fast.
- **Health Check Route:** SmartMart Analytics has a `/health` endpoint that Render probes to ensure zero downtime during redeployments.
- **File Persistence Note:** On Render free web services, the filesystem is ephemeral (resets on restart). Cleaned snapshots and uploaded datasets for your presentation are pre-loaded in the git repository (`data/processed/` and `data/raw/`) and persistent warehouse transactions reside safely in your cloud MySQL database.
