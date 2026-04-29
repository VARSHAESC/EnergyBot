# 🐳 EnergyBot Docker Deployment Guide

This guide explains how to run the **EnergyBot Infrastructure Platform** using Docker. This is the recommended way to share and run the project as it ensures all dependencies (AI models, Geospatial engines, and Routing backends) are perfectly configured.

## 📋 Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- At least 8GB of RAM allocated to Docker.
- An internet connection for the initial data download.

---

## 🚀 Getting Started

### 1. Environment Setup
The application requires an LLM API key to function.
1. Copy `.env.template` to a new file named `.env`.
2. Open `.env` and enter your API key:
   ```env
   LLM_API_KEY=your_key_here
   ```

### 2. Prepare Map Data (One-time Setup)
The project uses a local OSRM routing engine for street-accurate mapping.
1. Run the setup script:
   ```bash
   ./setup_osrm.bat
   ```
2. Wait for it to finish. This will download the regional map data (~180MB) and process it for the routing engine.

### 3. Launch the Platform
Build and start the containers using Docker Compose:
```bash
docker compose up --build -d
```

### 4. Access the App
Once the containers are running, open your browser to:
- **Application**: [http://localhost:8600](http://localhost:8600)
- **Routing Engine Status**: [http://localhost:5000](http://localhost:5000)

---

## 🛠️ Troubleshooting

- **Map is empty?** Ensure `setup_osrm.bat` finished successfully and the `osrm_data` folder is not empty.
- **AI not responding?** Check your `.env` file and ensure the `LLM_API_KEY` is valid.
- **Port Conflict?** If port 8600 is taken, you can change it in the `compose.yaml` file under the `ports` section of the `app` service.

---

## 📂 Project Structure in Docker
- `app`: The Streamlit frontend and RAG engine logic.
- `osrm`: The Open Source Routing Machine backend serving street data.
- `volumes`: Your Excel data and database are mounted from the host, so changes to `excel_data/Hausanschluss_data.xlsx` are reflected in the app after clicking **"🔄 KI-Speicher aktualisieren"**.
