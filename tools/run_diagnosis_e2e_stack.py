"""Run the diagnosis end-to-end check on a throwaway stack, including AI outages.

    python tools/run_diagnosis_e2e_stack.py --ai-python PATH --images FOLDER [--models DIR] [--mysqld PATH]

Run it with the Backend's Python (it needs Flask, PyMySQL and requests). It starts, all on
127.0.0.1: a new MySQL server on an empty data directory, the AI service with --ai-python on CPU,
and the Backend from this checkout. It then runs check_diagnosis_e2e.py, stops and restarts the AI
(down, without gatekeeper weights, busy), and compares count_diagnosis_outcomes.py with the
answers actually given.

--models holds the released weights in the layout of ai_service/experiments (default: that
folder). --images is described in check_diagnosis_e2e.py.

It never uses an existing database: AEGIS_* variables are removed, the Backend gets only the
temporary MySQL, and MQTT and Mongo delivery are off. Everything it writes goes to a new
temporary folder, which is kept for inspection; delete it when you no longer need it.
This checks behaviour, not model accuracy. Exit 1 if anything fails.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymysql
import requests
from pymysql.constants import CLIENT

REPO = Path(__file__).resolve().parents[1]
DETECTOR_WEIGHTS = Path("yolo/baseline_v4_50epochs/weights/best.pt")
GATE_WEIGHTS = Path("gatekeeper/gate_v1b/best.pt")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def clean_env(**extra):
    """The caller's environment without any AEGIS_ setting, so nothing points at a real install."""
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("AEGIS_")}
    env.update(PYTHONUTF8="1", **extra)
    return env


def stop(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        # A Windows venv python.exe is a launcher with the real interpreter as its child:
        # terminating only the launcher leaves the server listening for a few more seconds.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        process.terminate()
    try:
        process.wait(30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(30)


def wait_port_closed(port, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return
        time.sleep(0.2)
    raise TimeoutError(f"port {port} still accepts connections")


def find_mysqld():
    found = shutil.which("mysqld")
    if found:
        return Path(found)
    programs = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
    candidates = sorted((programs / "MySQL").glob("MySQL Server */bin/mysqld.exe"))
    return candidates[-1] if candidates else None


class Stack:
    def __init__(self, args, root):
        self.args, self.root, self.processes, self.results = args, root, [], {}
        self.ai_port, self.api_port, self.db_port = free_port(), free_port(), free_port()
        self.api = f"http://127.0.0.1:{self.api_port}"

    def check(self, name, passed, seen):
        self.results[name] = {"pass": bool(passed), "seen": str(seen)}
        print(f"{'pass' if passed else 'FAIL'}  {name}: {seen}", flush=True)

    def start(self, name, argv, env, cwd=None):
        with (self.root / f"{name}.log").open("ab") as log:
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=NO_WINDOW)
        self.processes.append((name, process))
        return process

    def wait_http(self, url, process, seconds=240):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"the process behind {url} exited; see the logs in {self.root}")
            try:
                return requests.get(url, timeout=5)
            except requests.RequestException:
                time.sleep(0.5)
        raise TimeoutError(url)

    # --- MySQL -----------------------------------------------------------------
    def admin(self):
        return pymysql.connect(host="127.0.0.1", port=self.db_port, user="root", password="", charset="utf8mb4",
                               autocommit=True, client_flag=CLIENT.MULTI_STATEMENTS)

    def start_mysql(self):
        data = self.root / "mysql-data"
        base = [str(self.args.mysqld), "--no-defaults"]
        subprocess.run(base + ["--initialize-insecure", f"--datadir={data}"], check=True, capture_output=True, timeout=300)
        self.mysqld = self.start("mysqld", base + [
            f"--datadir={data}", f"--port={self.db_port}", "--bind-address=127.0.0.1", "--mysqlx=0",
            "--default-time-zone=+00:00", "--character-set-server=utf8mb4",
            "--collation-server=utf8mb4_0900_ai_ci"], clean_env())
        for _ in range(180):
            try:
                self.admin().close()
                break
            except pymysql.Error:
                if self.mysqld.poll() is not None:
                    raise RuntimeError(f"mysqld exited; see {self.root / 'mysqld.log'}")
                time.sleep(1)
        self.password = uuid.uuid4().hex
        statements = ["CREATE DATABASE aegis_e2e CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci", "USE aegis_e2e"]
        statements += [p.read_text(encoding="utf-8") for p in sorted((REPO / "backend/database/mysql").glob("*.sql"))]
        for host in ("localhost", "127.0.0.1"):
            statements += [f"CREATE USER 'e2e'@'{host}' IDENTIFIED BY '{self.password}'",
                           f"GRANT ALL ON aegis_e2e.* TO 'e2e'@'{host}'"]
        with self.admin() as connection, connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)
                while cursor.nextset():
                    pass

    def count(self, table):
        with self.admin() as connection, connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM aegis_e2e.{table}")
            return cursor.fetchone()[0]

    # --- AI service --------------------------------------------------------------
    def prepare_ai(self, name, weights):
        """A copy of the AI service with exactly these weights, so the checkout is never written to."""
        target = self.root / name
        (target / "api").mkdir(parents=True)
        for source in (REPO / "ai_service/api").iterdir():
            if source.suffix in (".py", ".json"):
                shutil.copy2(source, target / "api" / source.name)
        for relative in weights:
            destination = target / "experiments" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.args.models / relative, destination)
        return target / "api" / "app.py"

    def start_ai(self, app, inflight=2):
        env = clean_env(AEGIS_AI_PORT=str(self.ai_port), AEGIS_AI_MAX_INFLIGHT=str(inflight),
                        CUDA_VISIBLE_DEVICES="-1", YOLO_OFFLINE="true", YOLO_AUTOINSTALL="false")
        process = self.start("ai", [str(self.args.ai_python), "-B", str(app)], env)
        return process, self.wait_http(f"http://127.0.0.1:{self.ai_port}/health", process)

    def stop_ai(self, process):
        stop(process)
        wait_port_closed(self.ai_port)

    # --- Backend -----------------------------------------------------------------
    def start_backend(self):
        config = dict(STORAGE_BACKEND="mysql", UPLOAD_DIR=str(self.root / "uploads"),
                      MYSQL=dict(host="127.0.0.1", port=self.db_port, user="e2e", password=self.password,
                                 database="aegis_e2e"),
                      AI_API_URL=f"http://127.0.0.1:{self.ai_port}", MONGO_DELIVERY_ENABLED=False,
                      DETECT_USER_LIMIT=1000, BACKEND_MAX_INFLIGHT=6, REGISTER_IP_LIMIT=100, LOGIN_IP_LIMIT=100)
        code = ("import json,os; from app import create_app; from werkzeug.serving import make_server; "
                "app=create_app(json.loads(os.environ['E2E_CONFIG'])); "
                f"make_server('127.0.0.1',{self.api_port},app,threaded=True).serve_forever()")
        env = clean_env(E2E_CONFIG=json.dumps(config), AEGIS_MQTT_ENABLED="0", AEGIS_MONGO_DELIVERY_ENABLED="0")
        self.backend = self.start("backend", [sys.executable, "-B", "-c", code], env, cwd=REPO / "backend")
        self.wait_http(self.api + "/health", self.backend)

    # --- scenarios -----------------------------------------------------------------
    def run(self):
        full = self.prepare_ai("ai-full", [DETECTOR_WEIGHTS, GATE_WEIGHTS])
        without_gate = self.prepare_ai("ai-without-gatekeeper", [DETECTOR_WEIGHTS])
        self.start_mysql()
        ai, health = self.start_ai(full)
        body = health.json()
        self.check("AI ready with both released models",
                   health.status_code == 200 and body.get("model_pinned") and body["gatekeeper"].get("pinned"),
                   f"HTTP {health.status_code} {body.get('status')} {body['gatekeeper'].get('version')}")
        users_before = self.count("users")
        self.start_backend()

        report_path = self.root / "contract.json"
        done = subprocess.run([sys.executable, "-B", str(REPO / "tools/check_diagnosis_e2e.py"), "--url", self.api,
                               "--images", str(self.args.images), "--json", str(report_path)],
                              capture_output=True, text=True, encoding="utf-8", timeout=1800, env=clean_env())
        if not report_path.is_file():
            raise RuntimeError("the contract check produced no report:\n" + done.stderr[-2000:])
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.check("contract check through the Backend", done.returncode == 0,
                   f"{report['checks']} checks, {report['failed']} failed, outcomes {report['outcomes']}")
        for failure in report["failures"][:15]:
            print("      -", failure)
        self.check("the Backend is using the temporary database", self.count("users") >= users_before + 2,
                   f"accounts in the temporary database: {self.count('users')}")
        answered = report["ai_answers"]

        credentials = {"email": f"outage-{uuid.uuid4().hex}@example.test", "password": "e2e-" + uuid.uuid4().hex}
        requests.post(self.api + "/api/auth/register", json=credentials, timeout=30).raise_for_status()
        token = requests.post(self.api + "/api/auth/login", json=credentials, timeout=30).json()["access_token"]
        accepted = [p for p in sorted(self.args.images.iterdir()) if p.name.startswith(self.args.outage_image_prefix)]
        image = (accepted or sorted(self.args.images.iterdir()))[0].read_bytes()

        def detect(key):
            return requests.post(self.api + "/api/disease/detect", files={"image": ("x.jpg", image)}, timeout=120,
                                 headers={"Authorization": "Bearer " + token, "Idempotency-Key": key})

        def code_of(response):
            return response.status_code, (response.json().get("error") or {}).get("code")

        self.stop_ai(ai)
        down = detect("outage-key")
        ai, _ = self.start_ai(full)
        back = detect("outage-key")
        answered += back.status_code == 200
        self.check("AI down then back: the same key succeeds",
                   code_of(down) == (503, "ai_unavailable") and back.status_code == 200,
                   f"down={code_of(down)} retry={code_of(back)}")

        self.stop_ai(ai)
        degraded, health = self.start_ai(without_gate)
        refused = detect("gate-key")
        self.stop_ai(degraded)
        ai, _ = self.start_ai(full, inflight=1)
        after = detect("gate-key")
        answered += after.status_code == 200
        self.check("AI without gatekeeper, then restored: the same key succeeds",
                   health.status_code == 503 and code_of(refused) == (503, "ai_gatekeeper_unavailable")
                   and after.status_code == 200,
                   f"health={health.status_code} refused={code_of(refused)} retry={code_of(after)}")

        busy, unexpected, rounds = [], [], 0
        while not busy and rounds < 5:
            rounds += 1
            barrier = threading.Barrier(5)

            def burst(number):
                barrier.wait(timeout=30)
                key = f"busy-{rounds}-{number}"
                return key, detect(key)

            with ThreadPoolExecutor(max_workers=5) as pool:
                for key, response in pool.map(burst, range(5)):
                    answered += response.status_code == 200
                    if code_of(response) == (503, "ai_busy"):
                        busy.append(key)
                    elif response.status_code != 200:
                        unexpected.append(code_of(response))
        retried = []
        for key in busy:
            response = detect(key)
            answered += response.status_code == 200
            retried.append(response.status_code)
        self.check("AI busy, then retried with the same key", bool(busy) and set(retried) == {200} and not unexpected,
                   f"rounds={rounds} busy={len(busy)} retry statuses={sorted(set(retried))} unexpected={unexpected}")

        stop(self.backend)
        counted = subprocess.run([sys.executable, "-B", str(REPO / "tools/count_diagnosis_outcomes.py"),
                                  str(self.root / "backend.log")], capture_output=True, text=True, encoding="utf-8",
                                 env=clean_env())
        summary = json.loads(counted.stdout)
        self.check("the log count equals the answers the AI gave",
                   counted.returncode == 0 and summary["diagnoses"] == answered,
                   f"counted={summary['diagnoses']} answered={answered} unreadable={summary['unreadable_events']}")
        log_text = (self.root / "backend.log").read_text(encoding="utf-8", errors="replace")
        self.check("no traceback or account email in the Backend log",
                   "Traceback" not in log_text and "@example.test" not in log_text,
                   f"tracebacks={log_text.count('Traceback')} emails={log_text.count('@example.test')}")
        self.upload_ms = report["accepted_upload_ms"]

    def close(self):
        for name, process in self.processes:
            if name != "mysqld":
                stop(process)
        if getattr(self, "mysqld", None) is not None and self.mysqld.poll() is None:
            try:
                with self.admin() as connection, connection.cursor() as cursor:
                    cursor.execute("SHUTDOWN")
                self.mysqld.wait(90)
            except Exception:
                stop(self.mysqld)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ai-python", type=Path, required=True, help="Python of the AI service environment")
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--models", type=Path, default=REPO / "ai_service/experiments")
    ap.add_argument("--mysqld", type=Path, default=find_mysqld())
    ap.add_argument("--outage-image-prefix", default="blast",
                    help="the outage scenarios upload the first image whose name starts with this")
    a = ap.parse_args()
    for label, path in [("--ai-python", a.ai_python), ("--images", a.images), ("--mysqld", a.mysqld),
                        ("detector weights", a.models / DETECTOR_WEIGHTS), ("gatekeeper weights", a.models / GATE_WEIGHTS)]:
        if path is None or not Path(path).exists():
            ap.error(f"{label} not found: {path}")
    a.images, a.models = a.images.resolve(), a.models.resolve()
    root = Path(tempfile.mkdtemp(prefix="aegis-e2e-"))
    print(f"temporary stack in {root}")
    stack = Stack(a, root)
    try:
        stack.run()
    except Exception as error:  # report it as a failed run, with the logs kept
        stack.check("the stack ran to the end", False, f"{type(error).__name__}: {error}")
    finally:
        stack.close()
        (root / "results.json").write_text(json.dumps(stack.results, indent=2, ensure_ascii=False), encoding="utf-8")
    failed = [name for name, result in stack.results.items() if not result["pass"]]
    print("accepted upload ms:", getattr(stack, "upload_ms", None))
    print(f"logs and results kept in {root}")
    print("E2E RESULT:", "PASS" if not failed else "FAIL: " + "; ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
