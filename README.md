streamlit run dashboard/streamlit_app.py
python start_neuroplant.py

python -m src.layer1_ingestion.mqtt_publisher
python -m src.layer1_ingestion.mqtt_subscriber

python -m venv .venv
.venv\Scripts\activate

dir /S /B D:\Anuj\neuroplant-ai | findstr /V ".venv" | findstr /V "__pycache__" > structure.txt

dir /S /B D:\Anuj\neuroplant-ai | findstr /V /I ".venv" | findstr /V /I "__pycache__" | findstr /V /I "digital-twin\node_modules" | findstr /V /I "digital-twin\dist" | findstr /V /I "tests" | findstr /V /I "outputs" | findstr /V /I "notebooks" | findstr /V /I "docker" > structure.txt

cd D:\Anuj\neuroplant-ai

# fpdf fix
pip uninstall -y fpdf fpdf2
pip install fpdf2
python -c "import fpdf; print(fpdf.__file__)"

# work_orders table
python -m src.layer3_oee.models

# seed scripts
type nul > scripts\__init__.py
python -m scripts.seed_sku_cycle_times
python -m scripts.seed_demo_oee_data

# diagnose genai fallback
python -m src.layer10_genai_assistant.query_router