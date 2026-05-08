from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import lionscliapp as app

from lions_eco import __version__


ECOLOGY_FILE = "ecology.json"
RUN_FILE = "ECO-RUN.json"
ECO_VERSION = "1.0"
RUN_VERSION = "1.0"


def main():
    declare_app()
    app.main()


def declare_app():
    app.declare_app("eco", __version__)
    app.describe_app("Crystallize executable directory trees into timestamped run directories.")
    app.declare_projectdir(".eco")

    app.declare_key("execpath.ecology", "")
    app.declare_key("execpath.rundir", "runs")
    app.declare_key("json.indent.run", 2)

    app.describe_key("execpath.ecology", "Source ecology directory containing ecology.json")
    app.describe_key("execpath.rundir", "Directory where timestamped run directories are created")
    app.describe_key("json.indent.run", "Indent level for ECO-RUN.json")

    app.declare_cmd("run", cmd_run)
    app.describe_cmd("run", "Copy an ecology into a fresh run directory and execute it")


def cmd_run():
    runtime = read_runtime_config()
    ecology = read_ecology(runtime["ecology"])
    validate_ecology(ecology)
    validate_run_relationship(runtime["ecology"], runtime["rundir"])

    run = prepare_run(runtime, ecology)
    print(f"eco run: {run['run-id']}")
    print(f"run directory: {run['run-path']}")

    try:
        result = execute_run(run, ecology)
        if result.returncode == 0:
            finish_run(run, "COMPLETE", result.returncode)
            print("eco status: COMPLETE")
        else:
            finish_run(run, "FAILED", result.returncode)
            print(f"eco status: FAILED ({result.returncode})")
    except Exception as exc:
        finish_run(run, "FAILED", None, str(exc))
        raise


def read_runtime_config():
    ecology = app.ctx["execpath.ecology"]
    rundir = app.ctx["execpath.rundir"]
    if not ecology.exists():
        raise FileNotFoundError(f"Ecology directory does not exist: {ecology}")
    if not ecology.is_dir():
        raise NotADirectoryError(f"Ecology path is not a directory: {ecology}")
    return {
        "ecology": ecology,
        "rundir": rundir,
    }


def read_ecology(ecology_path):
    path = ecology_path / ECOLOGY_FILE
    if not path.exists():
        raise FileNotFoundError(f"Missing {ECOLOGY_FILE}: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_ecology(ecology):
    if not isinstance(ecology, dict):
        raise ValueError("ecology.json must contain a JSON object")
    require_value(ecology, "eco-version", ECO_VERSION)
    execution = require_dict(ecology, "execution")
    require_value(execution, "entry-type", "subprocess")

    cwd = require_string(execution, "cwd")
    if Path(cwd).is_absolute():
        raise ValueError("execution.cwd must be relative to the copied run directory")

    command = execution.get("command")
    if not isinstance(command, list) or not command:
        raise ValueError("execution.command must be a non-empty array")
    for item in command:
        if not isinstance(item, str):
            raise ValueError("execution.command items must be strings")

    environment = execution.get("environment", {})
    if environment is None:
        return
    if not isinstance(environment, dict):
        raise ValueError("execution.environment must be an object when present")
    for key, value in environment.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("execution.environment keys and values must be strings")


def require_value(data, key, expected):
    value = data.get(key)
    if value != expected:
        raise ValueError(f"{key} must be {expected!r}")
    return value


def require_dict(data, key):
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def require_string(data, key):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def validate_run_relationship(ecology_path, rundir):
    if ecology_path == rundir:
        raise ValueError("rundir must not be the ecology directory")
    try:
        rundir.relative_to(ecology_path)
    except ValueError:
        return
    raise ValueError("rundir must not be inside the ecology directory")


def prepare_run(runtime, ecology):
    runtime["rundir"].mkdir(parents=True, exist_ok=True)
    run_id = allocate_run_id(runtime["rundir"])
    run_path = runtime["rundir"] / run_id
    shutil.copytree(runtime["ecology"], run_path)

    run = {
        "run-id": run_id,
        "run-path": run_path,
        "source-ecology": runtime["ecology"],
        "created-at": str(time.time()),
        "execution": ecology["execution"],
    }
    write_run_file(run, "RUNNING")
    return run


def allocate_run_id(rundir):
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    index = 0
    while True:
        run_id = f"{date_prefix}_run-{index:04d}"
        if not (rundir / run_id).exists():
            return run_id
        index += 1


def execute_run(run, ecology):
    execution = ecology["execution"]
    cwd = resolve_execution_cwd(run["run-path"], execution["cwd"])
    env = build_environment(execution)
    return subprocess.run(
        execution["command"],
        cwd=str(cwd),
        env=env,
    )


def resolve_execution_cwd(run_path, cwd_text):
    cwd = (run_path / cwd_text).resolve()
    try:
        cwd.relative_to(run_path.resolve())
    except ValueError as exc:
        raise ValueError("execution.cwd must stay inside the copied run directory") from exc
    if not cwd.exists():
        raise FileNotFoundError(f"execution.cwd does not exist in run directory: {cwd}")
    if not cwd.is_dir():
        raise NotADirectoryError(f"execution.cwd is not a directory: {cwd}")
    return cwd


def build_environment(execution):
    env = os.environ.copy()
    env.update(execution.get("environment", {}) or {})
    return env


def finish_run(run, status, return_code, error=None):
    write_run_file(run, status, return_code, error)


def write_run_file(run, status, return_code=None, error=None):
    data = {
        "eco-run-version": RUN_VERSION,
        "run-id": run["run-id"],
        "created-at": run["created-at"],
        "source-ecology": str(run["source-ecology"]),
        "status": status,
        "execution": {
            "entry-type": run["execution"]["entry-type"],
            "cwd": run["execution"]["cwd"],
            "command": run["execution"]["command"],
        },
    }
    if status != "RUNNING":
        data["completed-at"] = str(time.time())
        data["return-code"] = return_code
    if error is not None:
        data["error"] = error

    indent = int(app.ctx.get("json.indent.run", 2))
    write_json_atomic(run["run-path"] / RUN_FILE, data, indent)


def write_json_atomic(path, data, indent):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    if indent <= 0:
        text = json.dumps(data, separators=(",", ":"))
    else:
        text = json.dumps(data, indent=indent)
    tmp_path.write_text(text + "\n", encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    main()
