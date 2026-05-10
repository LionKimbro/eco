import json
import sys
from types import SimpleNamespace

import lions_eco.cli as eco


def write_ecology(path, command, cwd="."):
    path.mkdir()
    (path / "ecology.json").write_text(
        json.dumps(
            {
                "eco-version": "1.0",
                "execution": {
                    "entry-type": "subprocess",
                    "cwd": cwd,
                    "command": command,
                },
            }
        ),
        encoding="utf-8",
    )


def test_prepare_run_copies_ecology_and_writes_running_file(tmp_path, monkeypatch):
    monkeypatch.setitem(eco.app.ctx, "json.indent.run", 2)
    source = tmp_path / "source"
    rundir = tmp_path / "runs"
    write_ecology(source, [sys.executable, "-c", "print('hello')"])
    (source / "asset.txt").write_text("copied", encoding="utf-8")

    ecology = eco.read_ecology(source)
    run = eco.prepare_run({"ecology": source, "rundir": rundir}, ecology)

    assert run["run-id"].endswith("_run-0000")
    assert (run["run-path"] / "asset.txt").read_text(encoding="utf-8") == "copied"
    metadata = json.loads((run["run-path"] / "ECO-RUN.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "RUNNING"
    assert metadata["execution"]["command"] == [sys.executable, "-c", "print('hello')"]


def test_execute_run_happens_inside_copied_directory(tmp_path, monkeypatch):
    monkeypatch.setitem(eco.app.ctx, "json.indent.run", 2)
    source = tmp_path / "source"
    rundir = tmp_path / "runs"
    write_ecology(
        source,
        [
            sys.executable,
            "-c",
            "from pathlib import Path; Path('made.txt').write_text('ok', encoding='utf-8')",
        ],
    )

    ecology = eco.read_ecology(source)
    run = eco.prepare_run({"ecology": source, "rundir": rundir}, ecology)
    result = eco.execute_run(run, ecology)
    eco.finish_run(run, "COMPLETE", result.returncode)

    assert result.returncode == 0
    assert not (source / "made.txt").exists()
    assert (run["run-path"] / "made.txt").read_text(encoding="utf-8") == "ok"
    metadata = json.loads((run["run-path"] / "ECO-RUN.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "COMPLETE"
    assert metadata["return-code"] == 0


def test_validate_rejects_rundir_inside_ecology(tmp_path):
    source = tmp_path / "source"
    source.mkdir()

    try:
        eco.validate_run_relationship(source, source / "runs")
    except ValueError as exc:
        assert "rundir must not be inside" in str(exc)
    else:
        raise AssertionError("expected validation failure")


def test_read_times_requires_positive_integer(monkeypatch):
    monkeypatch.setitem(eco.app.ctx, "times", "3")
    assert eco.read_times() == 3

    monkeypatch.setitem(eco.app.ctx, "times", "0")
    try:
        eco.read_times()
    except ValueError as exc:
        assert "at least 1" in str(exc)
    else:
        raise AssertionError("expected validation failure")


def test_cmd_run_performs_multiple_runs_in_series(tmp_path, monkeypatch):
    monkeypatch.setitem(eco.app.ctx, "execpath.ecology", tmp_path / "source")
    monkeypatch.setitem(eco.app.ctx, "execpath.rundir", tmp_path / "runs")
    monkeypatch.setitem(eco.app.ctx, "times", "3")
    monkeypatch.setitem(eco.app.ctx, "json.indent.run", 2)
    write_ecology(tmp_path / "source", [sys.executable, "-c", "print('hello')"])

    monkeypatch.setattr(eco, "execute_run", lambda run, ecology: SimpleNamespace(returncode=0))

    eco.cmd_run()

    run_dirs = sorted((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 3
    assert run_dirs[0].name.endswith("_run-0000")
    assert run_dirs[1].name.endswith("_run-0001")
    assert run_dirs[2].name.endswith("_run-0002")
    for run_dir in run_dirs:
        metadata = json.loads((run_dir / "ECO-RUN.json").read_text(encoding="utf-8"))
        assert metadata["status"] == "COMPLETE"


def test_cmd_run_stops_series_after_failure(tmp_path, monkeypatch):
    monkeypatch.setitem(eco.app.ctx, "execpath.ecology", tmp_path / "source")
    monkeypatch.setitem(eco.app.ctx, "execpath.rundir", tmp_path / "runs")
    monkeypatch.setitem(eco.app.ctx, "times", "3")
    monkeypatch.setitem(eco.app.ctx, "json.indent.run", 2)
    write_ecology(tmp_path / "source", [sys.executable, "-c", "print('hello')"])

    results = [0, 7, 0]

    def fake_execute_run(run, ecology):
        return SimpleNamespace(returncode=results.pop(0))

    monkeypatch.setattr(eco, "execute_run", fake_execute_run)

    eco.cmd_run()

    run_dirs = sorted((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 2
    first = json.loads((run_dirs[0] / "ECO-RUN.json").read_text(encoding="utf-8"))
    second = json.loads((run_dirs[1] / "ECO-RUN.json").read_text(encoding="utf-8"))
    assert first["status"] == "COMPLETE"
    assert second["status"] == "FAILED"
    assert second["return-code"] == 7
