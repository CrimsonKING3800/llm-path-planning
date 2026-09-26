# Multi-Agent Path Planning LLM Pipeline (PoC)

This document explains the architecture, workflow, logic, and results of the Proof of Concept (PoC) for generating and self-correcting multi-agent path planning algorithms using an LLM.

## 1. High-Level Overview

The goal of this system is to instruct a Large Language Model (LLM) to write a Python algorithm that can navigate multiple agents from start positions to goal positions on a grid without colliding with each other or obstacles. 

Because LLMs rarely write perfect multi-agent algorithms on the first try, this pipeline implements an **autonomous self-correction loop**. It executes the generated code, analyzes the exact nature of any failures, and feeds that feedback directly back into the LLM so it can fix its own code.

The pipeline is coordinated by an orchestrator (`run_poc.py`) and is broken into three main stages:
1. **Stage A: Generation & Correction (`algorithm_gen.py`)**
2. **Stage B: Execution & Validation (`simulator.py`)**
3. **Stage C: Interpretation (`interpret.py`)**

---

## 2. Component Logic and Workflow

### The Orchestrator (`run_poc.py`)
This script acts as the main driver:
- **Objective Configuration**: Defines grid size, agent counts, start/goal coordinates, static obstacles, movement rules, and optimization objectives.
- **Multiprocessing Isolation & Timeout**: Runs generated algorithms inside an isolated worker process (`_run_plan_in_worker`) with a strict 10-second execution timeout (`_execute_code_with_timeout`) to safely guard against infinite loops or blocking code.
- **Best Partial Result Tracking**: Tracks the best-performing code candidate (`best_result`) across retries—prioritizing minimal collisions and maximum goal completions—so that if retries are exhausted, the best attempt metrics are reported rather than the last failure.
- **Retry Management**: Enforces a budget (default: 3 attempts per run) for static, runtime, illegal move, or logic corrections before finalizing the run.

### Stage A: Generation & Correction (`algorithm_gen.py`)
This module interacts directly with the local LLM (`qwen2.5:7b` via Ollama) to produce and refine code:
- **Initial Prompting**: Prompts the LLM with environment specs, coordinate formatting guidelines (tuples vs. lists), movement constraints, and strict output rules (no trailing execution code).
- **AST Sanitization (`_extract_and_clean_code`)**: Parses raw LLM text using Python's `ast` (Abstract Syntax Tree), verifies code syntax, ensures a top-level `plan()` function exists, and strips out non-definition code (e.g., test calls or `if __name__ == '__main__':` blocks).
- **Four-Pronged Correction Paths**:
  1. **Static Validation Retry**: Retries immediately if generated text fails AST syntax parsing or omits the `plan()` function signature.
  2. **Runtime Error Correction**: Captures tracebacks and stack traces from execution crashes and prompts the LLM to fix the exception.
  3. **Illegal Move Correction**: Detects movement rule violations (e.g., non-adjacent steps or illegal diagonal moves based on 4-connected or 8-connected settings) and instructs the LLM with valid movement rules.
  4. **Logic / Collision Correction**: Feeds back vertex collision details, unreached goal lists, makespan, and total distance to guide structural algorithm fixes when code executes without crashing.

### Stage B: Simulation & Validation (`simulator.py`)
This module independently tests the LLM-generated code without relying on the model's self-reported success:
- **Execution Interface (`run_simulation`)**: Dynamically invokes `plan(grid_size, starts, goals, obstacles, constraints)` and captures output paths.
- **Independent Validation (`validate_paths`)**: Evaluates paths frame-by-frame for legal execution:
  - **Start & Goal Verification**: Ensures each agent starts at its designated origin and ends at its assigned target.
  - **Grid & Obstacle Constraints**: Verifies no agent moves out of bounds or steps on static obstacle cells.
  - **Movement Constraints**: Enforces 4-connected (Manhattan distance ≤ 1) or 8-connected max-distance bounds.
  - **Vertex Collisions**: Flags timesteps where two or more agents occupy the exact same cell.
  - **Edge / Swap Collisions**: Flags timesteps where two agents swap positions simultaneously between adjacent steps.
- **Metrics Computation**: Measures per-agent steps, overall makespan, and total distance.
- **Animation (`animate_paths`)**: Uses `matplotlib` to render and save an animated GIF (`first_success_animation.gif`) of agent trajectories for the first fully successful run.

### Stage C: Interpretation (`interpret.py`)
After simulation retries conclude (whether successful or exhausted), final metrics are formatted and sent to the LLM. The model returns a plain-language summary addressing whether the objective was met, probable causes for any remaining collisions/failures, and recommendations for algorithm improvement.

---

## 3. Data Logging and Observability

The system maintains end-to-end visibility into performance and model iteration:
- **Attempt History**: Saves every code iteration, failure diagnosis, and collision count across all attempts within each run.
- **Per-Run JSON Logs**: Writes full execution details, attempt histories, and LLM interpretations to `results/run_<id>.json`.
- **CSV Summary**: Compiles batch statistics into `results_summary.csv`, recording success flags (`code_ran`, `collision_free`, `all_goals_reached`), makespan, distance, collision counts, model name, and total attempts used.

---

## 4. Results & Performance

Running this pipeline on the local `qwen2.5:7b` model demonstrates autonomous algorithm design capabilities:
- **High Initial Success**: The model frequently achieves 0-collision, full-success runs on the first attempt for standard grid layouts.
- **Correction Loop Efficacy**: Targeted prompt feedback effectively guides the model to fix runtime exceptions, syntax issues, and collision bugs within 1–2 correction cycles.
- **Observed Bottlenecks**: Complex corridor bottlenecks with multiple agents sometimes exceed the tight 3-attempt budget when delicate prioritization logic is required.

This PoC demonstrates that an LLM can effectively write, execute, validate, and debug spatial-reasoning algorithms in an entirely automated pipeline.

