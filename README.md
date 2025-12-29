

# 🌶️ Paprika: Cognitive AI Agent Sandbox

![Status](https://img.shields.io/badge/Status-Prototype-orange)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.124%2B-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/AI-LangGraph-FF4B4B)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Unity](https://img.shields.io/badge/Frontend-Unity_2022-black?logo=unity&logoColor=white)

**Paprika** is an experimental AI agent framework that simulates **embodied cognition** inside a Unity kitchen.  
It decouples the **Brain** (Python + LangGraph backend) from the **Body** (Unity), letting agents perceive the world, plan tasks, execute actions, and receive critique through a real-time bridge.


## Why Paprika

- **Brain/Body split**: keep game logic in Unity, decision-making in Python.
- **Tool-based action**: agent can only act via a small set of tools (`move_to`, `pickup`, `put_down`, `chop`, `cook`).
- **Role-based control loop**: Mentor → Action → Critic → (optional) Skill/SOP writer.



## System Architecture

```text
  Unity (Body)  <------ WebSocket/HTTP ------>  FastAPI (Brain)
  - World state/perception                 - LangGraph graph
  - Physics + item transforms              - LLM planner + tool calls
  - Animation + movement                   - Critic / Mentor / Skill writer roles
```

### LLM Roles

* **Mentor (Planner)**: chooses the next task and outputs a strict JSON goal.
* **Action Agent (Executor)**: outputs a JSON list of tool calls with a `thought_trace`.
* **Critic (Verifier)**: checks success strictly from world state (no guessing).
* **Scribe (SOP Writer)**: converts action logs into reusable skills/SOP steps.



## Quickstart

> **Prereqs:** Docker + Docker Compose
> (Optional for local dev: Python 3.11+ and `uv`)

### 1) Configure environment

Create `.env` in the repo root:

```bash
# LLM
OPENAI_API_KEY=...

OLLAMA_BASE_URL=...
OLLAMA_API_KEY=...
OLLAMA_MODEL=gemma3:4b

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=...
LANGCHAIN_PROJECT=paprika-agent

# OpenWeather (optional tool)
OPENWEATHER_API_KEY=...
OPENWEATHER_BASE_URL=https://api.openweathermap.org
```

### 2) Start services

```bash
docker compose up -d --build
```


update shcema
```
make migrate
```
or use
```
docker compose exec agent-runtime alembic stamp head 
```
### 3) Enable pgvector (recommended: auto-init)

Paprika stores embeddings in Postgres (`VECTOR(...)`), so the `vector` extension must exist.
monitor
```
docker exec -it paprika_db psql -U admin -d paprika_ai
```


Create:

`docker/db/init/01_pgvector.sql`

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Mount it in your `db` service in `docker-compose.yml`:

```yaml
volumes:
  - backend_postgres_data:/var/lib/postgresql/data
  - ./docker/db/init:/docker-entrypoint-initdb.d
```

Reset **once** (init scripts only run on a fresh DB volume):

```bash
docker compose down -v
docker compose up -d --build
```

### 4) Run migrations

```bash
make migration msg="init_schema"
make migrate
```

## Unity Setup

Paprika’s backend refers to Unity objects by **ID**. These must match exactly.

### Valid IDs

| Category   | IDs                                                                       |
| ---------- | ------------------------------------------------------------------------- |
| Containers | `OnionBox`, `LettuceBox`, `CheeseBox`, `BreadBox`, `TomatoBox`, `MeatBox` |
| Stations   | `Oven`, `CutBoard`, `PlateBoard`, `Trash`                                 |
| Plates     | `Plate_agent_1`, `Plate_agent_2`, `Plate_agent_3`, `Plate_agent_4`        |

---

## Agent Actions (Tools)

The Action Agent must output a **valid JSON list**. Each step uses a tool and `{ "id": "..." }`.

### Supported tools

| Tool           | Meaning                            |
| -------------- | ---------------------------------- |
| `move_to(id)`  | Walk to a specific location/object |
| `pickup(id)`   | Pick up an item                    |
| `put_down(id)` | Put down an item                   |
| `chop(id)`     | Chop an ingredient                 |
| `cook(id)`     | Cook an item using an appliance    |

### Example: pick up meat and place on oven

```json
[
  {
    "thought_trace": "1. Go to MeatBox to grab meat",
    "function": "move_to",
    "args": { "id": "MeatBox" }
  },
  {
    "thought_trace": "2. Pick up meat",
    "function": "pickup",
    "args": { "id": "MeatBox" }
  },
  {
    "thought_trace": "3. Walk to the Oven",
    "function": "move_to",
    "args": { "id": "Oven" }
  },
  {
    "thought_trace": "4. Place meat on Oven to cook",
    "function": "put_down",
    "args": { "id": "Oven" }
  }
]
```

## Perception Contract (recommended)

Avoid relying on “status summary” strings. Use structured fields so the agent can reason about transforms (Raw → Cooked).
Recommended fields:

* `held_item`
* `reachable_objects`
* `visible_objects`
* `containers` / `stations` states (ex: `is_on`, `held_item`)
* `execution_trace` (last actions + results)

<details>
<summary>Why structured perception matters</summary>

If your oven turns `RawMeat` into `CookedMeat`, a string like `held_item: CookedMeat` loses *how it got there*.
Structured fields or an event log (`transformed_from: RawMeat`) prevents “goal confusion”.

</details>


## Missions

Current mission: **Make a Hamburger** (gather → process → assemble).

* Cook meat: `MeatBox → Oven → wait → pickup`
* Chop onion: `OnionBox → CutBoard → chop → pickup`
* Assemble on plate: `Bread + Cheese + prepared ingredients → Plate_agent_X`


## Folder Structure

> Replace the tree below with your real output (`tree -L 3`)

```bash
backend/
  app/
    agents/
    tools/
  alembic/
frontend/
  RestaurantGame3DUnity/
    Assets/
      Scripts/
```


## Extending Paprika

### Add a new tool

1. Add a schema in `app/tools/schemas.py`
2. Add a `ToolBuilder` in `app/tools/...` using `@tool_registry.register`
3. Implement the corresponding Unity action handler and ensure IDs match

### Add a new mission

* Update Mentor rules (task selection / goal format)
* Add Critic win-condition (success definition)
* Optional: add SOP/Skill writer rule if you want reusable skills

## Troubleshooting

### `type "vector" does not exist`

Enable pgvector:

```bash
docker compose exec db psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

If you want it automatic, use `docker-entrypoint-initdb.d` as described above.

### Init script error: “Is a directory”

You mounted a folder to a file path. You should mount the **init directory**:

```yaml
- ./docker/db/init:/docker-entrypoint-initdb.d
```

And ensure `01_pgvector.sql` is a **file**, not a folder.


## License
MIT License


## Support & Contact

When opening an issue, include:

* OS (macOS/Windows/Linux)
* `docker compose logs -f`
* last ~20 agent actions + critic output


If you want, paste your **real repo tree** (top 3 levels) + the actual **backend entrypoint** (e.g., `backend/app/main.py`) and I’ll replace the placeholders in “Folder Structure” + “How to Run” with exact commands and paths.

