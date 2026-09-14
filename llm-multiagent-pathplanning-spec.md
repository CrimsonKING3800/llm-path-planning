# LLM-Driven Multi-Agent Path Planning — PoC Design Spec

**Purpose:** Scoped design for a minimal proof-of-concept implementing the flow:
`Objective → LLM generates algorithm → Multi-agent execution → LLM interprets results`

This doc is meant to (1) hand to Antigravity as a build spec, and (2) serve as prep notes
for discussion with Preeth and for the check-in with Sir.

---

## 1. Overall Flow

```
[User/Objective] 
      ↓
[Stage A: LLM Algorithm Generation]  — LLM writes a Python function implementing
      ↓                                a multi-agent path planning strategy
[Stage B: Multi-Agent Simulator]     — executes the generated algorithm on N agents
      ↓                                in a grid world, logs trajectories/collisions/time
[Stage C: LLM Result Interpretation] — LLM reads the logs, explains outcomes,
      ↓                                flags failures, suggests refinements
[Report / next iteration]
```

Key design decision up front: **the LLM is called twice per run** (algorithm generation,
result interpretation), not once per timestep. This is the core difference from the
MSDTMD-SG paper (Xiao et al.), where the LLM is the per-step controller. Worth stating
explicitly to Sir: this is a complementary approach, not a replacement — it trades
per-step interpretability/adaptivity for much lower inference cost and a reusable,
inspectable algorithm artifact (actual code you can audit, unlike a fine-tuned model's
implicit policy).

---

## 2. Stage A — Objective → Algorithm

### 2.1 Objective schema (structured, not free text)

Keep this structured so the LLM has a well-defined contract. Free-text objectives are a
V2 feature once the structured pipeline works.

```json
{
  "grid_size": [20, 20],
  "num_agents": 5,
  "starts": [[0,0], [0,1], [0,2], [0,3], [0,4]],
  "goals": [[19,19], [19,18], [19,17], [19,16], [19,15]],
  "obstacles": [[5,5], [5,6], [5,7], [10,10]],
  "constraints": {
    "avoid_agent_collisions": true,
    "max_steps": 100,
    "movement": "4-connected"   // or "8-connected"
  },
  "objective": "minimize_makespan"   // or "minimize_total_distance", "minimize_max_delay"
}
```

### 2.2 Algorithm-generation prompt (template)

```
You are designing a multi-agent path planning algorithm.

Given:
- A grid of size {grid_size}
- {num_agents} agents with start positions {starts} and goal positions {goals}
- Static obstacles at {obstacles}
- Constraints: {constraints}
- Objective: {objective}

Write a single Python function `plan(grid_size, starts, goals, obstacles, constraints) 
-> List[List[Tuple[int,int]]]` that returns a list of paths (one per agent, as a list of 
(x,y) coordinates from start to goal). The function must:
1. Avoid static obstacles.
2. Avoid inter-agent collisions at every timestep (no two agents in the same cell,
   no swapping positions).
3. Use only the Python standard library (no external deps).
4. Be self-contained and runnable as-is.

Return ONLY the function code, no explanation.
```

**Known risk to test for:** LLM-generated code may not compile, may not actually avoid
collisions, or may hang on larger agent counts. This is the central feasibility question —
budget real time to test this against 5, 10, 20 agents before reporting back to Sir.

### 2.3 Fallback / safety net

Since generated code is arbitrary, run it:
- In a subprocess with a timeout (e.g., 10s)
- With output validated against a checker (see Stage B.2) before trusting results
- If generation fails validation N times, fall back to a known baseline (e.g., simple
  A* + priority ordering) so the pipeline doesn't just dead-end — useful for demoing.

---

## 3. Stage B — Multi-Agent Simulator

### 3.1 Interface

Minimal grid-world simulator (this is the piece Antigravity can scaffold quickly):

```python
def run_simulation(plan_fn, grid_size, starts, goals, obstacles, constraints):
    paths = plan_fn(grid_size, starts, goals, obstacles, constraints)
    # replay paths step by step, check for:
    #   - collisions with obstacles
    #   - collisions between agents (same cell, or swap)
    #   - agents reaching goals
    #   - steps taken per agent
    return {
        "success": bool,
        "collisions": [...],
        "steps_per_agent": [...],
        "makespan": int,
        "total_distance": int,
        "paths": paths
    }
```

### 3.2 Validator ("checker")

A separate, hand-written (not LLM-generated) function that independently verifies the
returned paths are legal — don't trust the generated algorithm's own claims of success.
This is what makes Stage C's interpretation meaningful rather than just parroting
whatever the algorithm claims.

### 3.3 Suggested tooling

- Pure Python + a simple matplotlib/plotly animation for visual sanity checks — no need
  for Gazebo/AirSim at PoC stage, that's overkill and adds setup risk.
- Log everything to a JSON results file per run for Stage C to consume.

---

## 4. Stage C — Results → Interpretation

### 4.1 Interpretation prompt (template)

```
You designed a multi-agent path planning algorithm for this objective: {objective}.

Execution results:
- Success: {success}
- Collisions detected: {collisions}
- Makespan: {makespan} steps
- Total distance: {total_distance}
- Per-agent steps: {steps_per_agent}

Explain in plain language:
1. Did the algorithm achieve the stated objective?
2. If there were failures/collisions, what likely caused them?
3. Suggest one concrete change to the algorithm to improve the result.
```

Output of this stage is both a human-readable report and (optionally, V2) a structured
suggestion that could feed back into Stage A for an automatic refinement loop.

---

## 5. Minimal PoC Scope (what to actually build first)

To keep this testable before the call with Sir / Prof Alexandre:

1. Hardcode ONE objective (5 agents, 20x20 grid, a few obstacles, minimize makespan).
2. Stage A: single LLM call → generated `plan()` function.
3. Stage B: run it in the simulator, validate independently.
4. Stage C: single LLM call → interpretation of the JSON result.
5. Run this end-to-end 5–10 times and note: how often does generated code even run
   without errors? How often is it collision-free? How does path quality compare to a
   hand-written A* baseline?

That failure/success rate across repeated runs **is** the feasibility answer Sir is
asking for — bring those numbers to the discussion, not just "it worked once."

---

## 6. Open Questions to Raise with Preeth / Sir

- Should the generated algorithm be regenerated fresh every run, or should successful
  algorithms be cached/reused as a library the LLM can pick from (cheaper, more reliable,
  but less "novel" per objective)?
- Is there a role for the per-step fine-tuned approach (MSDTMD-SG) as a fallback
  controller when the LLM-generated algorithm fails mid-execution — i.e., hybrid system?
- What's the comparison baseline for "success" — classical CBS/A* multi-agent planners
  will likely outperform LLM-generated code on correctness. Is the point efficiency,
  interpretability, generalization to novel objectives, or something else? Worth
  clarifying with Sir what the actual research contribution is meant to be.
- Related work to check before the call: LLMs generating optimization
  heuristics/algorithms (e.g., FunSearch-style approaches, EvoPrompting, "LLM as
  algorithm designer" literature) — useful for framing novelty and known failure modes.

---

## 7. Instruction Block for Antigravity (build request)

> Build a Python PoC with three modules:
> 1. `algorithm_gen.py` — calls an LLM (Llama via API/local endpoint) with the prompt
>    template in Section 2.2, extracts the returned Python function, and saves it to
>    a file with basic static validation (does it parse, does it define `plan()`).
> 2. `simulator.py` — implements the interface in Section 3.1, plus an independent
>    validator per Section 3.2, plus a simple matplotlib animation of agent paths.
> 3. `interpret.py` — calls an LLM with the prompt template in Section 4.1 on the JSON
>    results from simulator.py.
> Include a `run_poc.py` that wires all three together for the single hardcoded
> objective in Section 5, and runs it N times (configurable), logging success/failure
> rate and collision rate across runs to a summary CSV.
> Use only standard library + matplotlib + requests (for LLM API calls). No simulation
> frameworks (Gazebo/AirSim) at this stage.