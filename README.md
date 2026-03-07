# RPBOT Sandbox

A sandbox for experimenting with the **RPBOT** agent architecture. The project consists of a **Next.js** frontend, a **FastAPI** backend that runs the simulation engine, and the **RPBOT‑rpmodule** that implements the agent’s perception, planning, and control logic.

---

## Architecture Overview

```
+-------------------+          +-------------------+          +-------------------+
|  Next.js Frontend | <------> |  FastAPI Backend  | <------> |  RPBOT‑rpmodule   |
+-------------------+          +-------------------+          +-------------------+
        ▲                               ▲                           ▲
        │                               │                           │
        │  HTTP (REST)                  │  HTTP (REST)              │  Python API
        │                               │                           │
```

* **Next.js** – A React‑based UI that renders a 3D scene with `three.js` and provides controls for the user to interact with the simulation.
* **FastAPI** – Exposes REST endpoints for starting/stopping the simulation, retrieving agent status, and streaming events. It also hosts the simulation loop that updates the world state.
* **RPBOT‑rpmodule** – A Python package that implements the agent’s perception, planning, and control logic. It communicates with the simulation via the FastAPI backend.

---

## Setup & Run Instructions

The repository contains two separate projects: `frontend` and `backend`. Each has its own dependencies.

### 1. Clone the repository

```bash
git clone https://github.com/ricobiz/RPBOT-sandbox.git
cd RPBOT-sandbox
```

### 2. Install the backend

```bash
cd backend
pip install -r requirements.txt
```

> **Tip**: If you are using a virtual environment, activate it before running the above command.

### 3. Install the frontend

```bash
cd ../frontend
npm install
```

### 4. Configure the OpenRouter API key

The RPM module uses the OpenRouter API for language model calls. Create a file named `.env` in the `backend` directory with the following content:

```
OPENROUTER_API_KEY=your_api_key_here
```

> **Important**: Do **not** commit this file to version control. The key is kept secret.

### 5. Run the backend

```bash
cd backend
uvicorn main:app --reload
```

The backend will start on `http://127.0.0.1:8000`.

### 6. Run the frontend

```bash
cd ../frontend
npm run dev
```

The frontend will start on `http://localhost:3000` and will automatically connect to the backend.

---

## OpenRouter API Configuration

The RPM module expects the OpenRouter API key to be available as the environment variable `OPENROUTER_API_KEY`. The key is read when the module is imported, so you only need to set it once before launching the backend.

If you prefer to use a different key for a specific run, you can override the environment variable on the command line:

```bash
OPENROUTER_API_KEY=another_key uvicorn main:app --reload
```

---

## Simulation Loop, Perception, and Agent Control Flow

The simulation runs in a continuous loop on the backend. Each iteration performs the following steps:

1. **Perception** – The RPM module queries the simulation state (positions, velocities, sensor data) via the FastAPI API. It then processes this data into a structured observation.
2. **Planning** – Using the observation, the RPM module calls the OpenRouter language model to generate a high‑level plan or action sequence.
3. **Control** – The plan is translated into low‑level control commands (e.g., steering, acceleration) and sent back to the simulation via the FastAPI API.
4. **State Update** – The simulation engine updates the world state based on the control commands and physics.
5. **Event Streaming** – Any significant events (e.g., collisions, goal reached) are emitted through a WebSocket endpoint so the frontend can update the UI in real time.

The frontend visualises the world state and allows the user to pause, resume, or reset the simulation. All communication between the frontend and backend is performed over HTTP/REST, while the simulation loop itself runs on the backend.

---

## Contributing

Feel free to open issues or pull requests. Please follow the existing coding style and add tests where appropriate.

---

## License

MIT License. See `LICENSE` for details.
