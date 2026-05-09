# eco

`eco` is a small filesystem-native execution runner for Python projects.

It takes a directory that describes how to run itself, copies that directory into
a fresh timestamped run folder, runs the copied version, and records what
happened.

The core idea is simple:

1. You keep a source directory, called an ecology.
2. The ecology contains an `ecology.json` file.
3. `eco` copies the whole ecology into a run directory.
4. `eco` executes the command named in `ecology.json`.
5. The original source directory is left alone.

This is useful when you want each run of a program, experiment, script bundle, or
asset-processing setup to leave behind a complete inspectable copy of what ran.

## Why copy before running?

Many programs produce files as they run. Some write logs, generated data,
temporary files, images, reports, or debug output. If those files are written
directly into the source tree, it can become hard to tell what belongs to the
program and what was produced by a particular run.

`eco` avoids that by treating the copied run directory as the execution
environment. Your source ecology is the template. The run directory is the
working copy.

After a run, you can open the run directory in Explorer, Finder, a terminal, or
your editor and inspect exactly what happened.

## Basic Usage

Run an ecology like this:

```powershell
eco --execpath.ecology F:/mills/fantasy-scene/src --execpath.rundir F:/mill-runs run
```

On Linux or macOS, the same command shape applies:

```bash
eco --execpath.ecology ~/mills/fantasy-scene/src --execpath.rundir ~/mill-runs run
```

The two important settings are:

`execpath.ecology`
: The source ecology directory. This directory must contain `ecology.json`.

`execpath.rundir`
: The parent directory where `eco` creates timestamped run directories.

These names come from `lionscliapp`. The `execpath.` prefix means the value is
automatically interpreted as a filesystem path, expanded, and resolved before
`eco` uses it.

## Persistent Settings

`eco` uses `lionscliapp`, so settings can be saved between runs.

For example, you can save your usual run directory:

```powershell
eco set execpath.rundir F:/mill-runs
```

Then future commands can omit it:

```powershell
eco --execpath.ecology F:/mills/fantasy-scene/src run
```

The saved configuration is stored in a `.eco` directory under the place where
you run `eco`.

## The Ecology Directory

An ecology is just a directory tree. `eco` does not care whether it contains
Python modules, scripts, images, prompts, JSON files, CSV files, shell scripts,
or anything else.

The only required file is:

```text
ecology.json
```

That file tells `eco` how to start the ecology after it has been copied.

## ecology.json

A minimal `ecology.json` looks like this:

```json
{
  "eco-version": "1.0",
  "execution": {
    "entry-type": "subprocess",
    "cwd": ".",
    "command": ["python", "-m", "runtime.run"]
  }
}
```

The fields are:

`eco-version`
: The ecology format version. For now, this must be `"1.0"`.

`execution.entry-type`
: The execution mechanism. For now, this must be `"subprocess"`.

`execution.cwd`
: The working directory for the command, relative to the copied run directory.
Use `"."` to run from the top of the copied ecology.

`execution.command`
: The command list passed to Python's `subprocess.run()`. Each item is one
argument. Do not write this as one shell string.

For example, this:

```json
["python", "-m", "runtime.run"]
```

means:

```bash
python -m runtime.run
```

The list form is intentional. It works more predictably across Windows, Linux,
and macOS than a single command string.

## Environment Variables

An ecology can optionally provide environment variables for its command:

```json
{
  "eco-version": "1.0",
  "execution": {
    "entry-type": "subprocess",
    "cwd": ".",
    "command": ["python", "run.py"],
    "environment": {
      "MODE": "demo",
      "OUTPUT_FORMAT": "json"
    }
  }
}
```

These values are added to the normal process environment for the run.

## Run Directories

Run directories are created inside `execpath.rundir`.

Their names look like this:

```text
2026-05-08_run-0000
2026-05-08_run-0001
2026-05-08_run-0002
```

The date is the local calendar date. The run number starts at `0000` each day
and increases as more runs are created.

Inside each run directory, `eco` writes:

```text
ECO-RUN.json
```

This file records metadata for the run, including:

```json
{
  "eco-run-version": "1.0",
  "run-id": "2026-05-08_run-0000",
  "created-at": "1778277300.8311403",
  "source-ecology": "F:\\mills\\fantasy-scene\\src",
  "status": "COMPLETE",
  "execution": {
    "entry-type": "subprocess",
    "cwd": ".",
    "command": ["python", "-m", "runtime.run"]
  },
  "completed-at": "1778277300.9051921",
  "return-code": 0
}
```

The status is one of:

`RUNNING`
: The run has been created and execution has started.

`COMPLETE`
: The command exited with return code `0`.

`FAILED`
: The command exited with a non-zero return code, or `eco` hit an execution
error.

## A Tiny Example

Create a folder like this:

```text
hello-ecology/
  ecology.json
  run.py
```

`run.py`:

```python
from pathlib import Path

Path("hello-output.txt").write_text("Hello from eco!\n", encoding="utf-8")
print("wrote hello-output.txt")
```

`ecology.json`:

```json
{
  "eco-version": "1.0",
  "execution": {
    "entry-type": "subprocess",
    "cwd": ".",
    "command": ["python", "run.py"]
  }
}
```

Run it:

```powershell
eco --execpath.ecology ./hello-ecology --execpath.rundir ./runs run
```

Afterward, you should see a new directory under `runs/`. That directory contains
a copy of `run.py`, a copy of `ecology.json`, the generated
`hello-output.txt`, and `ECO-RUN.json`.

The original `hello-ecology/` directory remains unchanged.

## Installing for Development

From the repository root:

```powershell
python -m pip install -e .
```

Then run:

```powershell
eco help
```

You can also run without installing by setting `PYTHONPATH` to include `src` and
using:

```powershell
python -m lions_eco --execpath.ecology ./hello-ecology --execpath.rundir ./runs run
```

## What eco Does Not Do

`eco` intentionally does not define workflows, pipelines, dependency graphs, or
scheduling.

It only does this:

1. Read `ecology.json`.
2. Allocate a run directory.
3. Copy the ecology into it.
4. Run the declared command there.
5. Record the result.

That narrowness is part of the design. Other systems can build richer behavior
on top of `eco`, while `eco` remains easy to understand and inspect.
