# eco

`eco` is a small filesystem-native execution runner.

It copies an ecology directory into a timestamped run directory, writes
`ECO-RUN.json`, executes the command declared in `ecology.json`, and updates the
run metadata with the final status.

```powershell
eco --execpath.ecology F:/mills/fantasy-scene/src --execpath.rundir F:/mill-runs run
eco set execpath.rundir F:/mill-runs
eco --execpath.ecology F:/mills/fantasy-scene/src run
```

An ecology directory must contain `ecology.json`:

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
