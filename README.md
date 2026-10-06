<div align="center">
    <h1>GRETH</h1>
    <h3>Grater Than is Autonomous AI Hacking Adversary Opperation</h3>
    <b>An open-source AI Hacking to penetrate any system.</b>
</div>

Filesystem tools are restricted to the mounted workspace. To inspect sandbox system
binary directories such as `/usr/bin`, use the read-only `container_list_dir` tool.
Its supported paths are explicitly allow-listed; file writes remain workspace-only.

## Running

```sh
uv run python -m greth --target <target> --objective "<objective>"
```

Tool results are printed in the terminal and saved in the run's `artifacts/` directory.
If a tool reports an error or a command exits unsuccessfully, GRETH displays and saves
that result, then stops the workflow instead of continuing with later tool calls.
