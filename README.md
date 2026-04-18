# 🏛️ Bharat Bricks — AI Civic Complaint Management System

> AI-Powered Multi-Department Complaint Routing for Madhya Pradesh Government  
> Built for the **Databricks Hackathon 2026 · Nyaya-Sahayak Track**

---

## What It Does

Bharat Bricks lets citizens file civic complaints in plain language. The AI automatically:

1. **Classifies** the complaint to the correct government department (54 MP departments)
2. **Routes** it to one or more governing bodies via Multi-Body Router
3. **Tracks** priority and estimated resolution time
4. **Chatbot** lets citizens interact conversationally and file complaints via BharatBot

---

## Architecture

```
Citizen UI (Gradio)
     │
     ├── Complaint Classifier  →  Department prediction (TF-IDF + LogisticRegression)
     ├── Multi-Body Router     →  Routes to 1–N governing bodies (LangChain + Groq)
     ├── RAG Chatbot           →  FAISS + sentence-transformers (multilingual)
     └── Admin Panel           →  Officer login, status updates, AI audit trail
          │
     Delta Lake (Databricks)   ←→   MLflow (model registry)
          │
     SQLite (local dev mode)
```

**Cloud stack:** Databricks Free Edition · Delta Lake · Apache Spark MLlib · MLflow · Model Serving · Databricks Apps  
**AI stack:** scikit-learn · LangChain · Groq (llama-3.3-70b) · FAISS · sentence-transformers  
**Frontend:** Gradio · FastAPI

---

## Quick Start (Local)

### 1. Clone the repo

```bash
git clone https://github.com/IITI-tushar/BharatBricks.git
cd BharatBricks
```

### 2. Create virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment (optional)

```bash
cp .env.example .env
# Edit .env with your Databricks workspace URL, token, and Groq API key
```

### 5. Initialize database

```bash
# Windows
set PYTHONUTF8=1 && python database.py

# Mac / Linux
PYTHONUTF8=1 python database.py
```

### 6. Run the app

```bash
# Windows
set PYTHONUTF8=1 && python app_local.py

# Mac / Linux
PYTHONUTF8=1 python app_local.py
```

Open your browser at: **http://127.0.0.1:7861/**

Admin panel password: `admin123`

---

## Hosting on Databricks (Cloud)

### Prerequisites
- Databricks Free Edition account
- Unity Catalog enabled (`bharat_bricks.civic` schema)
- Groq API key (free at console.groq.com)

### Step 1 — Run setup notebooks in order

| Notebook | Purpose |
|----------|---------|
| `00_setup_tables` | Create 10 Delta tables in Unity Catalog |
| `00_seed_governing_bodies` | Seed all 54 MP department records |
| `01_train_classifier` | Train TF-IDF + LogisticRegression classifier, register to MLflow |
| `02_multi_body_router` | Deploy LangChain + Groq router as Model Serving endpoint |
| `03_rag_chatbot` | Build FAISS index on Volume, embed 4000+ complaints |
| `04_analytics` | Run K-Means clustering on complaints |
| `05_analytics_dashboard` | Render analytics in notebook widgets |
| `06_interactive_demo` | Live AI tester widget + department health check |

### Step 2 — Deploy Model Serving endpoints

1. Go to **Serving** in your Databricks workspace
2. Create endpoint: `complaint-classifier` → attach registered MLflow model
3. Create endpoint: `multi-body-router-endpoint` → attach router pyfunc model
4. Set compute: **CPU · Small** (free tier compatible)

### Step 3 — Deploy Gradio as Databricks App

```bash
# In your Databricks workspace terminal
databricks apps create bharat-bricks-app
databricks apps deploy bharat-bricks-app --source-code-path /path/to/app
```

Or via UI: **Compute → Apps → Create App → Upload files**

### Step 4 — Configure environment variables in the App

```
DATABRICKS_HOST      = https://your-workspace.azuredatabricks.net
DATABRICKS_TOKEN     = your-personal-access-token
GROQ_API_KEY         = your-groq-api-key
BODY_NAME            = Madhya Pradesh State Governing Body
BODY_ID              = GB001
```

### Step 5 — Wire the SQL Warehouse

In your `.env` or App config:
```
SQL_WAREHOUSE_ID = your-warehouse-id
```

Find it at: **SQL Warehouses → your warehouse → Connection details → HTTP path**

---

## Hosting on a VPS / Cloud VM

### Option A — Direct Python

```bash
git clone https://github.com/IITI-tushar/BharatBricks.git
cd BharatBricks
pip install -r requirements.txt
PYTHONUTF8=1 python app_local.py
```

Then open port 7861 in your firewall/security group.

### Option B — Run as a background service (Linux)

Create `/etc/systemd/system/bharatbricks.service`:

```ini
[Unit]
Description=Bharat Bricks Civic App
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/BharatBricks
ExecStart=/home/ubuntu/BharatBricks/venv/bin/python app_local.py
Restart=always
Environment=PYTHONUTF8=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable bharatbricks
sudo systemctl start bharatbricks
```

### Option C — Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PYTHONUTF8=1
EXPOSE 7861
CMD ["python", "app_local.py"]
```

```bash
docker build -t bharatbricks .
docker run -p 7861:7861 bharatbricks
```

---

## Tabs & Features

| Tab | Description |
|-----|-------------|
| 📝 Submit Complaint | File a complaint — AI classifies & routes instantly, shows full AI reasoning |
| 💬 AI Chatbot | BharatBot — conversational complaint filing with live AI pipeline output |
| 📋 View All Complaints | Public feed with status badges, priority, department, progress bars |
| 🔍 Track Complaint | Track by Complaint ID, add public support votes |
| 🏛️ Admin Panel | Officer login (`admin123`), update status, view AI audit trail per complaint |
| 📊 Statistics | Live counts by status, top supported complaints |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABRICKS_HOST` | Cloud only | Workspace URL |
| `DATABRICKS_TOKEN` | Cloud only | Personal access token |
| `GROQ_API_KEY` | Cloud only | For LangChain + Groq router |
| `BODY_NAME` | Optional | Governing body display name |
| `BODY_ID` | Optional | e.g. `GB001` |
| `TREASURY_EMAIL` | Optional | Treasury notification address |

---

## Team

Built for Databricks Hackathon 2026 — IIT Indore

---

## License

MIT
