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
This script acts as the main driver. It takes an objective configuration (grid size, agents, start/goal coordinates, obstacles) and manages multiple runs of the pipeline (e.g., 5 or 10 runs). For each run, it orchestrates the A \u2192 B \u2192 C stages and handles the retry limits (maximum of 3 attempts per run). 

### Stage A: Generation (`algorithm_gen.py`)
This module interacts directly with the local LLM (`qwen2.5:7b` via Ollama) to produce the code.
- **Initial Generation**: The LLM is provided with a strict prompt defining the grid environment, the constraints (4-connected movement, obstacle avoidance), and a requirement to write a specific `plan(objective)` function. 
- **AST Sanitization**: The raw text output from the LLM is parsed using Python's `ast` (Abstract Syntax Tree) to extract only the valid Python code and drop any conversational filler.
- **Three-Pronged Correction Paths**: If the code fails during Stage B, it is routed to one of three specialized correction prompts based on the exact failure type:
  1. **Runtime Error Correction**: If the code crashes or has a syntax error, the LLM receives the stack trace and the exact exception.
  2. **Illegal Move Correction**: If an agent jumps across the map or moves diagonally, the LLM is told exactly which move was illegal and reminded of the 4-connected rules.
  3. **Logic / Collision Correction**: If the code runs flawlessly but agents collide or fail to reach their goals, the LLM is given the simulation statistics and told to fix its collision-avoidance logic.

### Stage B: Simulation & Validation (`simulator.py`)
This module is the testing ground for the generated algorithm.
- **Execution**: It imports the LLM's `plan()` function dynamically and runs it with a strict timeout to prevent infinite loops.
- **Validation**: It steps through the returned paths frame by frame to verify:
  - Agents don't step out of bounds or into obstacles.
  - Agents only make valid adjacent moves (or wait in place).
  - Agents don't occupy the same cell at the same time, nor do they swap locations directly (edge collisions).
- **Metrics**: It calculates the makespan (time to finish), total distance traveled, and counts the total collisions.
- **Animation**: For the first entirely successful run, it uses `matplotlib` to render and save a visual animation of the paths.

### Stage C: Interpretation (`interpret.py`)
After the execution attempt loop ends (either by succeeding or failing after 3 attempts), the final statistics (collisions, steps, makespan) are passed back to the LLM. The LLM translates these raw metrics into a plain-English diagnostic report, determining if the objective was met and what likely caused any failures.

---

## 3. Data Logging and History Tracking

The system is designed for high observability so we can see exactly how the LLM improves:
- **Attempt History**: Inside `run_poc.py`, every single code version generated across all attempts (including the corrections) is saved into a list. This allows us to track exactly what the LLM changed from attempt 1 to attempt 3.
- **Per-Run JSON**: All data (the generated code history, final paths, LLM interpretations) is saved to a detailed `results/<run_id>.json` file.
- **CSV Summary**: A final `results_summary.csv` is compiled at the end of the batch. It records boolean success flags, collision counts, the number of attempts used, and the model name for easy evaluation.

---

## 4. Results & Performance

Running this pipeline on the local `qwen2.5:7b` model yields impressive results for a small model:
- **High Initial Success**: The model frequently achieves 0-collision, full-success runs on the very first attempt. In a recent 5-run batch, 3 out of 5 runs were solved perfectly on attempt 1.
- **Correction Efficacy**: The three-pronged correction loop successfully salvages runs that crash on the first attempt by providing highly targeted feedback.
- **Limitations**: When the model struggles with complex logic (e.g., getting multiple agents stuck in a narrow corridor), it occasionally fails to resolve the bottleneck within the tight 3-attempt budget. 

This PoC demonstrates that an LLM can effectively write, execute, and debug its own spatial-reasoning algorithms entirely autonomously.
