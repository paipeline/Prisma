# LangGraph Studio Guide

LangGraph Studio gives you an interactive UI to inspect nodes, state transitions, and messages flowing through Prisma's `CodeReAct` workflow. The graph entry-point is exported in `studio.py`, and `langgraph.json` already points Studio to that object.

## Prerequisites

1. **Create / activate a virtual-env** (optional but recommended)

   ```bash
   python -m venv .venv && source .venv/bin/activate
   ```

2. **Install dependencies directly from `pyproject.toml`** (no `requirements.txt` needed):

   Using **uv** (fast drop-in replacement for `pip`):
   ```bash
   uv pip install -e .[dev]
   ```
   or with plain pip:
   ```bash
   pip install -e .[dev]
   ```

3. **Populate your `.env`** with the necessary API keys. A quick way is to start from the template:

   ```bash
   cp .env.example .env
   # then edit .env and add your keys (e.g. OPENAI_API_KEY)
   ```

## Launching the Studio

From the project root, simply run:

```bash
langgraph dev --open
```

The console will print the local API URL (default `http://127.0.0.1:2024`) and a link to open the Studio UI in your browser.

## Exploring the Workflow

1. Select the **agent** graph in the left panel.
2. Click **Run** to execute a workflow and watch each node fire in real-time.
3. Use the **State** tab to inspect the `AgentState` at every step.
4. Re-run or replay past executions to debug.

## Hot-reloading

Studio rebuilds your graph whenever you change Python files. If you add new packages or system dependencies, stop & restart `langgraph dev` so the environment can rebuild.

Happy debugging! :rocket:
