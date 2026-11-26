"""
start_neuroplant.py — NeuroPlant AI one-click launcher.

Runs everything the demo needs, in the right order, with health checks
between each step. Press Ctrl+C once to shut down all background services.

  python start_neuroplant.py

What starts, in order:
  1. External services (via docker-compose if present, else health-checked):
     - Redis        (Layer 1 cache)
     - PostgreSQL   (Layer 3 OEE / downtime / work orders)
     - Mosquitto    (Layer 1 MQTT broker)  [optional]
  2. OPC-UA server         -> opc.tcp://localhost:4840
  3. MQTT publisher        -> publishes simulated readings to Mosquitto
  4. MQTT subscriber       -> forwards readings to Redis + InfluxDB
  5. FastAPI backend       -> http://127.0.0.1:8000/docs
  6. Twin cache refresh    -> POST /twin/refresh (so /twin/machines works)
  7. Streamlit dashboard   -> http://localhost:8501  (foreground)
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# DEPENDENCY BOOTSTRAP
# ─────────────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    print("Installing missing dependency: requests")
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"],
                   check=False)
    import requests


# ─────────────────────────────────────────────────────────────────
# .ENV LOADER
# ─────────────────────────────────────────────────────────────────
def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(override=True)
        return
    except ImportError:
        pass

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
PYTHON = sys.executable

API_HOST, API_PORT = "127.0.0.1", 8000
STREAMLIT_PORT = 8501

OPCUA_PORT = 4840
MQTT_HOST, MQTT_PORT = "127.0.0.1", 1883

# Set True to force reseed of OEE + SKU tables on every launch
RESEED = False

# Set True to rebuild the digital twin on every launch
REBUILD_TWIN = False

BACKGROUND_PROCS: list[subprocess.Popen] = []

# ANSI colour helpers
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
B = "\033[1m"
RS = "\033[0m"


# ─────────────────────────────────────────────────────────────────
# OUTPUT HELPERS
# ─────────────────────────────────────────────────────────────────
def ok(msg):   print(f"  {G}✓{RS}  {msg}")
def warn(msg): print(f"  {Y}⚠{RS}  {msg}")
def err(msg):  print(f"  {R}✗{RS}  {msg}")
def info(msg): print(f"  {C}→{RS}  {msg}")


def run(cmd, title, cwd=None):
    print(f"\n{B}  {title}...{RS}")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode == 0:
        ok(f"{title} completed")
    else:
        warn(f"{title} exited with code {result.returncode}")
    return result.returncode == 0


# ─────────────────────────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────────────────────────
def banner():
    print(f"""
{C}{B}
  ███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗ ██████╗ ██╗      █████╗ ███╗   ██╗████████╗
  ████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗██╔══██╗██║     ██╔══██╗████╗  ██║╚══██╔══╝
  ██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║██████╔╝██║     ███████║██╔██╗ ██║   ██║
  ██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔═══╝ ██║     ██╔══██║██║╚██╗██║   ██║
  ██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝██║     ███████╗██║  ██║██║ ╚████║   ██║
  ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝
{RS}
  {B}     AI  —  Autonomous Manufacturing Intelligence & IIoT Platform{RS}
  {C}  Monitoring · Predictive Maintenance · Digital Twin · OEE · Energy · GenAI{RS}
""")


# ─────────────────────────────────────────────────────────────────
# PORT MANAGEMENT
# ─────────────────────────────────────────────────────────────────
def free_port(port: int):
    """Kill any process listening on `port` (Windows netstat / Unix lsof)."""
    if sys.platform.startswith("win"):
        try:
            result = subprocess.run(["netstat", "-ano"],
                                    capture_output=True, text=True)
            killed = set()
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    pid = line.strip().split()[-1]
                    if pid not in killed and pid != "0":
                        subprocess.run(["taskkill", "/F", "/PID", pid],
                                       capture_output=True)
                        killed.add(pid)
                        warn(f"Freed port {port} (killed stale PID {pid})")
        except Exception as e:
            warn(f"Could not check/free port {port}: {e}")
    else:
        try:
            result = subprocess.run(["lsof", "-ti", f":{port}"],
                                    capture_output=True, text=True)
            for pid in result.stdout.split():
                subprocess.run(["kill", "-9", pid])
                warn(f"Freed port {port} (killed stale PID {pid})")
        except Exception as e:
            warn(f"Could not check/free port {port}: {e}")


# ─────────────────────────────────────────────────────────────────
# SERVICE HEALTH
# ─────────────────────────────────────────────────────────────────
def wait_for_service(url: str, name: str, timeout: int = 30) -> bool:
    info(f"Waiting for {name} at {url} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.status_code < 500:
                ok(f"{name} is up  ({url})")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    err(f"{name} did not respond within {timeout}s")
    return False


def wait_for_tcp(host: str, port: int, name: str, timeout: int = 20) -> bool:
    import socket
    info(f"Waiting for {name} on {host}:{port} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                ok(f"{name} is listening")
                return True
        except OSError:
            time.sleep(0.5)
    err(f"{name} did not open {host}:{port} within {timeout}s")
    return False


# ─────────────────────────────────────────────────────────────────
# PYTHON / FILE CHECKS
# ─────────────────────────────────────────────────────────────────
def check_python():
    v = sys.version_info
    if v.major < 3 or (v.major == 3 and v.minor < 9):
        err(f"Python 3.9+ required. Found {v.major}.{v.minor}")
        sys.exit(1)
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


REQUIRED_FILES = [
    # Dashboard + pages
    "dashboard/streamlit_app.py",
    "pages/home.py",
    "pages/machine_monitoring.py",
    "pages/oee_analytics.py",
    "pages/predictive_maintenance.py",
    "pages/production_quality.py",
    "pages/energy_sustainability.py",
    "pages/genai_assistant.py",
    "dashboard/ui/topbar.py",
    "dashboard/ui/theme.py",
    "dashboard/ui/sidebar.py",
    "dashboard/ui/components.py",
    "dashboard/ui/charts.py",
    "dashboard/ui/animations.py",

    # FastAPI backend
    "src/api/main.py",
    "src/api/routers/twin.py",
    "src/api/routers/oee.py",
    "src/api/routers/monitoring.py",
    "src/api/routers/maintenance.py",
    "src/api/routers/alerts.py",
    "src/api/routers/energy.py",
    "src/api/routers/quality.py",
    "src/api/routers/assistant.py",

    # Ingestion layer
    "src/layer1_ingestion/opcua_server.py",
    "src/layer1_ingestion/opcua_client.py",
    "src/layer1_ingestion/mqtt_publisher.py",
    "src/layer1_ingestion/mqtt_subscriber.py",
    "src/layer1_ingestion/synthetic_sensor_generator.py",
    "src/layer1_ingestion/influxdb_writer.py",

    # Twin core
    "src/layer5_digital_twin/twin_state.py",
    "src/layer5_digital_twin/production_simulator.py",
    "src/layer5_digital_twin/downtime_impact_calculator.py",

    # OEE / persistence
    "src/layer3_oee/models.py",
    "src/layer3_oee/oee_calculator.py",
    "src/layer3_oee/downtime_classifier.py",

    # Config + settings
    "src/config/settings.py",
    "src/config/plant_topology.json",

    # Seed scripts
    "scripts/seed_sku_cycle_times.py",
    "scripts/seed_demo_oee_data.py",

    # Digital twin (built version is optional but its embed is required)
    "digital-twin/streamlit_integration/digital_twin_embed.py",

    ".env",
]


def check_files(base: Path) -> list:
    print(f"\n{B}  Checking project files...{RS}")

    # Auto-create missing __init__.py so imports resolve
    for init in [
        "dashboard/__init__.py",
        "dashboard/ui/__init__.py",
        "pages/__init__.py",
        "scripts/__init__.py",
        "src/__init__.py",
        "src/api/__init__.py",
        "src/api/routers/__init__.py",
        "src/config/__init__.py",
        "src/database/__init__.py",
        "src/layer1_ingestion/__init__.py",
        "src/layer3_oee/__init__.py",
        "src/layer4_predictive_maintenance/__init__.py",
        "src/layer5_digital_twin/__init__.py",
        "src/layer6_production_optimizer/__init__.py",
        "src/layer7_energy_intelligence/__init__.py",
        "src/layer8_quality_intelligence/__init__.py",
        "src/layer9_sustainability/__init__.py",
        "src/layer10_genai_assistant/__init__.py",
    ]:
        p = base / init
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("# auto-generated by start_neuroplant.py\n")
            ok(f"Created missing init: {init}")

    missing = []
    for rel in REQUIRED_FILES:
        p = base / rel
        if p.exists():
            ok(rel)
        else:
            err(f"MISSING: {rel}")
            missing.append(rel)
    return missing


# ─────────────────────────────────────────────────────────────────
# ENV CHECK
# ─────────────────────────────────────────────────────────────────
def check_env():
    print(f"\n{B}  Checking environment variables...{RS}")

    checks = [
        ("GEMINI_API_KEY", "GenAI assistant (Layer 10)"),
        ("POSTGRES_HOST",  "PostgreSQL (Layer 3)"),
        ("POSTGRES_DB",    "PostgreSQL database name"),
        ("POSTGRES_USER",  "PostgreSQL user"),
        ("POSTGRES_PASSWORD", "PostgreSQL password"),
        ("REDIS_HOST",     "Redis cache (Layer 1)"),
        ("REDIS_PORT",     "Redis port"),
        ("MQTT_BROKER_HOST", "MQTT broker host"),
        ("MQTT_BROKER_PORT", "MQTT broker port"),
        ("OPCUA_SERVER_URL", "OPC-UA server URL"),
        ("APP_SECRET_KEY", "FastAPI JWT secret"),
    ]
    for key, desc in checks:
        val = os.environ.get(key, "")
        if val:
            masked = val[:6] + "..." if len(val) > 8 else "(set)"
            ok(f"{key}  ({masked})")
        else:
            warn(f"{key} not set  —  {desc}")

    demo = os.environ.get("NEUROPLANT_DEMO_MODE", "false")
    if demo.lower() == "true":
        info("DEMO MODE is ON")
    else:
        info("DEMO MODE is OFF")


# ─────────────────────────────────────────────────────────────────
# DOCKER / EXTERNAL SERVICE BOOTSTRAP
# ─────────────────────────────────────────────────────────────────
def docker_available() -> bool:
    try:
        r = subprocess.run(["docker", "info"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def find_compose_file(base: Path) -> Path | None:
    for name in ("docker-compose.yml", "docker-compose.yaml",
                 "compose.yml", "compose.yaml"):
        p = base / name
        if p.exists():
            return p
    return None


def ensure_external_services():
    """Start docker-compose if present, else warn about missing services."""
    print(f"\n{B}  Checking external services...{RS}")

    compose = find_compose_file(ROOT)
    if compose and docker_available():
        info(f"Found {compose.name}. Starting stack via docker compose up -d ...")
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=ROOT,
        )
        if result.returncode == 0:
            ok("Docker stack started")
            time.sleep(4)  # let containers boot
        else:
            warn("docker compose up returned non-zero; continuing anyway")
    elif compose and not docker_available():
        warn("docker-compose.yml found but Docker daemon is not reachable.")
        warn("Start Docker Desktop, then re-run.")
    else:
        info("No docker-compose.yml found — checking running services directly")

    # Verify each service
    wait_for_tcp("127.0.0.1", int(os.environ.get("REDIS_PORT", 6379)),
                 "Redis", timeout=10)

    # Postgres check: TCP only (no DB creds tested here)
    wait_for_tcp(os.environ.get("POSTGRES_HOST", "127.0.0.1"),
                 int(os.environ.get("POSTGRES_PORT", 5432)),
                 "PostgreSQL", timeout=10)

    # MQTT — optional, warn only
    if not wait_for_tcp(MQTT_HOST, MQTT_PORT, "MQTT broker", timeout=5):
        warn("MQTT broker not running. Live sensor feed will show demo values.")


# ─────────────────────────────────────────────────────────────────
# DATABASE CHECK + SEED
# ─────────────────────────────────────────────────────────────────
def check_database_and_seed():
    print(f"\n{B}  Checking database & seeding...{RS}")
    try:
        from src.layer3_oee.models import SessionLocal, OEERecord, SKUCycleTime
    except Exception as e:
        err(f"Cannot import database models: {e}")
        warn("Skipping seed. Fix DB connection, then re-run.")
        return

    try:
        s = SessionLocal()
    except Exception as e:
        err(f"Cannot open DB session: {e}")
        warn("Ensure PostgreSQL is running and .env POSTGRES_* values are correct.")
        return

    try:
        sku_count = s.query(SKUCycleTime).count()
        oee_count = s.query(OEERecord).count()
        info(f"sku_cycle_times rows: {sku_count}")
        info(f"oee_records rows:     {oee_count}")
    except Exception as e:
        err(f"Query failed: {e}")
        s.close()
        return
    s.close()

    need_seed = RESEED or sku_count == 0 or oee_count == 0
    if not need_seed:
        ok("Database already seeded — skipping")
        return

    info("Seeding SKU cycle times ...")
    run([PYTHON, "-m", "scripts.seed_sku_cycle_times"], "SKU cycle-times seed")

    info("Seeding OEE + downtime demo data ...")
    run([PYTHON, "-m", "scripts.seed_demo_oee_data"], "OEE demo-data seed")


# ─────────────────────────────────────────────────────────────────
# DIGITAL TWIN BUILD CHECK
# ─────────────────────────────────────────────────────────────────
def ensure_twin_build():
    print(f"\n{B}  Checking digital twin build...{RS}")
    dist_index = ROOT / "digital-twin" / "dist" / "index.html"
    if dist_index.exists() and not REBUILD_TWIN:
        ok("digital-twin/dist/index.html found")
        return True

    warn("Twin build missing or rebuild requested")
    if not docker_available() and not shutil_which("npm"):
        err("npm not found on PATH — cannot build the twin.")
        info("Install Node.js, then run: cd digital-twin && npm install && npm run build")
        return False

    info("Running: npm install (if needed) && npm run build")
    dt = ROOT / "digital-twin"
    if not (dt / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=dt)
    result = subprocess.run(["npm", "run", "build"], cwd=dt)
    if result.returncode == 0:
        ok("Twin built successfully")
        return True
    else:
        err("Twin build failed — Streamlit twin tab will show 'build not found'")
        return False


def shutil_which(name: str) -> str | None:
    import shutil
    return shutil.which(name)


# ─────────────────────────────────────────────────────────────────
# BACKGROUND PROCESS LAUNCHERS
# ─────────────────────────────────────────────────────────────────
def launch_opcua() -> bool:
    print(f"\n{B}  Launching OPC-UA server (port {OPCUA_PORT})...{RS}")
    free_port(OPCUA_PORT)
    proc = subprocess.Popen(
        [PYTHON, "-m", "src.layer1_ingestion.opcua_server"],
        cwd=ROOT,
    )
    BACKGROUND_PROCS.append(proc)
    time.sleep(2.0)
    if proc.poll() is not None:
        err(f"OPC-UA server exited immediately (code {proc.returncode})")
        return False
    return wait_for_tcp("127.0.0.1", OPCUA_PORT, "OPC-UA server", timeout=15)


def launch_mqtt_publisher() -> bool:
    print(f"\n{B}  Launching MQTT publisher...{RS}")
    proc = subprocess.Popen(
        [PYTHON, "-m", "src.layer1_ingestion.mqtt_publisher"],
        cwd=ROOT,
    )
    BACKGROUND_PROCS.append(proc)
    time.sleep(1.5)
    if proc.poll() is not None:
        warn(f"MQTT publisher exited (code {proc.returncode}) — "
             f"check that Mosquitto is running on {MQTT_HOST}:{MQTT_PORT}")
        return False
    ok("MQTT publisher running")
    return True


def launch_mqtt_subscriber() -> bool:
    print(f"\n{B}  Launching MQTT subscriber...{RS}")
    proc = subprocess.Popen(
        [PYTHON, "-m", "src.layer1_ingestion.mqtt_subscriber"],
        cwd=ROOT,
    )
    BACKGROUND_PROCS.append(proc)
    time.sleep(1.5)
    if proc.poll() is not None:
        warn(f"MQTT subscriber exited (code {proc.returncode}) — "
             f"Redis may not be running")
        return False
    ok("MQTT subscriber running")
    return True


def launch_api() -> bool:
    api_file = ROOT / "src" / "api" / "main.py"
    if not api_file.exists():
        err("src/api/main.py not found — skipping FastAPI launch")
        return False

    print(f"\n{B}  Launching FastAPI backend (port {API_PORT})...{RS}")
    free_port(API_PORT)

    proc = subprocess.Popen(
        [
            PYTHON, "-m", "uvicorn",
            "src.api.main:app",
            "--host", API_HOST,
            "--port", str(API_PORT),
            "--reload",
        ],
        cwd=ROOT,
    )
    BACKGROUND_PROCS.append(proc)

    time.sleep(2.5)
    if proc.poll() is not None:
        err(f"FastAPI exited immediately (code {proc.returncode})")
        err("Common causes: import error in src/api/main.py, missing router,")
        err("broken DB connection, or the app object is not named 'app'.")
        return False

    return wait_for_service(
        f"http://{API_HOST}:{API_PORT}/docs", "FastAPI", timeout=25
    )


def refresh_twin_cache():
    """Trigger /twin/refresh so the twin has fresh OPC-UA state."""
    print(f"\n{B}  Refreshing digital-twin cache...{RS}")
    try:
        r = requests.post(
            f"http://{API_HOST}:{API_PORT}/twin/refresh", timeout=10
        )
        if r.status_code == 200:
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            ok(f"Twin cache refreshed — {data.get('machines_updated', '?')} machines")
        else:
            warn(f"Twin refresh returned {r.status_code} — twin may show 0 assets")
    except Exception as e:
        warn(f"Twin refresh failed: {e}")


# ─────────────────────────────────────────────────────────────────
# STREAMLIT (foreground)
# ─────────────────────────────────────────────────────────────────
def launch_streamlit():
    app = ROOT / "dashboard" / "streamlit_app.py"
    if not app.exists():
        err("dashboard/streamlit_app.py not found — cannot launch dashboard")
        sys.exit(1)

    free_port(STREAMLIT_PORT)

    print(f"\n{G}{B}  ✓ All checks passed. Launching NeuroPlant AI...{RS}")
    print(f"\n  {C}Dashboard  :  http://localhost:{STREAMLIT_PORT}{RS}")
    print(f"  {C}FastAPI    :  http://{API_HOST}:{API_PORT}/docs{RS}")
    print(f"  {C}OPC-UA     :  opc.tcp://localhost:{OPCUA_PORT}/neuroplant/server/{RS}")
    print(f"\n  Press  {B}Ctrl + C{RS}  to stop all services.\n")

    # Streamlit opens the browser automatically when --server.headless=false
    # and running locally. Setting it explicitly here.
    subprocess.run([
        PYTHON, "-m", "streamlit", "run", str(app),
        "--server.port",     str(STREAMLIT_PORT),
        "--server.headless", "false",
        "--server.address",  "localhost",
    ])


# ─────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────
def cleanup():
    print(f"\n{Y}  Shutting down background services...{RS}")
    for proc in BACKGROUND_PROCS:
        if proc.poll() is None:
            try:
                proc.terminate()
                ok(f"Terminated PID {proc.pid}")
            except Exception as e:
                warn(f"Could not terminate PID {proc.pid}: {e}")

    # On Windows give the OS a moment to release ports
    time.sleep(0.5)


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    banner()

    os.chdir(ROOT)
    info(f"Project root: {ROOT}")

    check_python()

    missing = check_files(ROOT)
    check_env()

    if missing:
        print(f"\n{R}{B}  ✗ {len(missing)} required file(s) missing. Cannot launch.{RS}")
        for f in missing:
            print(f"    {R}•{RS} {f}")
        print(f"\n  Fix the missing files above, then re-run:")
        print(f"  {C}python start_neuroplant.py{RS}\n")
        sys.exit(1)

    ensure_external_services()
    check_database_and_seed()
    ensure_twin_build()

    try:
        launch_opcua()
        launch_mqtt_publisher()
        launch_mqtt_subscriber()

        api_ok = launch_api()
        if not api_ok:
            warn("FastAPI did not start cleanly — twin + GenAI may show empty states")
            warn("Running in degraded mode. Dashboard will still launch.")
        else:
            refresh_twin_cache()

        launch_streamlit()

    except KeyboardInterrupt:
        print(f"\n{Y}  Interrupted by user.{RS}")
    finally:
        cleanup()


if __name__ == "__main__":
    main()