# LLM-A*: Large Language Model Enhanced Incremental Heuristic Search on Path Planning

This repository contains a Python implementation and evaluation framework for an LLM-guided path-planning approach, inspired by the method proposed in *"LLM-A*: Large Language Model Enhanced Incremental Heuristic Search on Path Planning"* (Meng et al., Findings of EMNLP 2024).

This project implements a 3D grid-based A* search that incorporates intermediate waypoints to guide the search. It includes a baseline Standard A* algorithm, an LLM integration layer for waypoint generation, and a suite of handcrafted failure cases to evaluate how waypoint guidance behaves under difficult spatial constraints.

## 1. Introduction and Project Overview

Conventional A* guarantees optimal paths when paired with an admissible heuristic. However, in complex environments with local minima (such as concave obstacles), purely geometric heuristics can draw the search into dense exploration, resulting in a large number of expanded nodes.

LLM-A* proposes addressing this by using Large Language Models to analyze the environment and suggest high-level waypoints. The algorithm then targets these waypoints sequentially. 

**Objectives of this Repository:**
*   Implement a waypoint-guided A* search supporting 3D grid environments.
*   Implement Dijkstra (zero-heuristic) and Standard A* baselines for independent optimality and performance comparison.
*   Evaluate the method under specifically designed "failure cases" (e.g., dead ends, bad waypoint ordering) to observe algorithmic weaknesses.

## 2. The Research Paper: Technique and Methodology

The paper *“LLM-A*: Large Language Model Enhanced Incremental Heuristic Search on Path Planning”* introduces a framework where an LLM acts as an incremental guide for heuristic search.

According to the methodology:
1.  The LLM is prompted with a textual representation of the environment.
2.  The LLM generates a sequence of intermediate waypoints.
3.  The search algorithm incorporates these waypoints into its priority function, aiming to pull the search toward the waypoint.

*(Note: Without access to the original paper's exact source code, this implementation builds upon the core conceptual framework described above. Specific mechanisms, such as map compression techniques, were interpreted and implemented independently.)*

## 3. My Implementation: Architecture and Technical Details

### Environment and State Representation
*   **Grid:** Represented as a discrete 3D spatial grid (`Grid3D` in `environment.py`).
*   **Connectivity:** Supports 26-connected movement. Diagonal corner-cutting through empty space is permitted.
*   **Cost Calculation:** Euclidean distance.

### Baselines
*   **Standard A*** (`standard_astar`): Prioritizes nodes using $f(n) = g(n) + h(n, goal)$. 
*   **Dijkstra Optimal Reference** (`dijkstra_search`): A zero-heuristic search ($h=0$). In our evaluation framework, this establishes the true geometric optimal cost to independently verify suboptimality claims.

### LLM-Guided A* Integration
*   **Inference:** Connects to a local Ollama API.
*   **Validation:** The `parse_and_validate_waypoints` function filters targets that are out-of-bounds, non-integral, or placed directly on obstacles.
*   **Fallback:** If the LLM times out or fails to return valid JSON, the algorithm defaults to an empty waypoint list, gracefully falling back to Standard A* behaviour.

### Priority Functions and Search Behavior
The implementation dynamically updates the target $t$. The modified priority function used to guide expansion is:
$$f(n) = g(n) + h(n, goal) + h(n, t)$$

This applies an increased heuristic weight toward the intermediate target $t$. 
The `config.py` provides variants:
*   `PRIORITY_VARIANT = "baseline"`: Maintains the formula above. If the final target $t$ is the global goal, this results in $g(n) + 2h(n, goal)$.
*   `PRIORITY_VARIANT = "standard_goal"`: Zeroes the target cost for the final leg to restore standard admissibility.

By adding $h(n, t)$ to a standard admissible heuristic, the overall heuristic often becomes inadmissible, sacrificing the guarantee of an optimal path in exchange for directional bias.

## 4. Code Structure

```text
llm-astar/
├── astar3d.py              # Core pathfinding algorithms (Standard A*, LLM-A*, Dijkstra)
├── config.py               # Global configurations, variants, grid definitions
├── environment.py          # 3D Grid representation, obstacle generation
├── failure_cases.py        # Definitions of specific benchmark grids and injected hypotheses
├── llm_planner.py          # LLM HTTP client, JSON parsing, prompt formatting
├── main.py                 # Normal-case end-to-end runner and JSON artifact dumper
├── run_failure_cases.py    # Automated benchmark runner for testing specific failure modes
├── tests/
│   └── test_astar.py       # Unit test suite for bounds, validation, and fallbacks
└── failure_results/        # Auto-generated artifacts and FAILURE_REPORT.md
```

## 5. Normal-Case Experiments

In a standard environment (e.g., a 100x100x50 grid with 25,000 obstacles), the full pipeline was tested. In the recorded artifact (`experiment_e7942193-17d1-4cdd-ac8a-7fbbeae9c6e2.json`), the LLM API timed out after 30 seconds, successfully triggering the fallback mechanism.

| Metric | Standard A* | LLM-A* (Timeout Fallback) |
|---|---|---|
| Path Cost | 145.09 | 145.09 |
| Nodes Expanded | 43,720 | 43,720 |
| Search Time | ~1.46s | ~1.38s |
| LLM Inference Time | N/A | ~32.08s (Timeout) |
| Total Pipeline Time | ~1.46s | ~33.47s |

This confirms that when LLM guidance fails, the algorithm safely reverts to Standard A* behaviour, matching the node expansions and path cost exactly.

## 6. Failure-Case Experiments (The Benchmark)

To evaluate the algorithmic properties of waypoint-guided search, we constructed 10 deliberate failure cases (`Case A` through `Case J`). These cases evaluate how injected waypoints interact with the priority function. Costs are independently compared to Dijkstra. 

*(Note: Cases A-D, F-J use manually injected waypoints to isolate algorithmic behaviour from LLM generation quality).*

**Key Observations from the Experiments:**

1.  **Higher Path Costs (Suboptimality)**
    *   **Case B (Misleading Wall):** A waypoint placed inefficiently behind a wall resulted in a path cost of `8.56`, compared to the Dijkstra optimal of `7.83` (Ratio: 1.09).
    *   **Case D (Dead-End):** A waypoint injected inside a dead-end forced backtracking, yielding a cost of `11.12` vs optimal `10.54`.
2.  **Increased Search Effort (Inefficiency)**
    *   **Case C (Narrow Corridor):** Guiding the search through a highly constrained space expanded 25 nodes, while unguided Standard A* found the identical path by expanding only 7 nodes.
    *   **Case F (Bad Waypoint Ordering):** Injecting valid waypoints in a "zig-zag" order forced the algorithm to expand 123 nodes to find a path that Standard A* found in just 7 nodes.
3.  **Correctness Checks**
    *   **Case J (Disconnected Grid):** In a grid strictly bisected by a wall, the target-switching logic safely exhausted the `OPEN` set without infinite looping, correctly identifying that no path exists.

## 7. Limitations of the Original Paper's Method

*We were unable to directly access the original paper to confirm exactly which limitations the authors explicitly identified. Therefore, the following are algorithmic constraints theoretically associated with this class of methods, rather than verified paper citations.*

1.  **LLM Spatial Hallucination:** LLMs often struggle to output precise, collision-free geometric coordinates based on text prompts.
2.  **Overhead of OPEN Reprioritization:** Dynamically changing the heuristic target during search requires updating the priority of nodes in the `OPEN` set, introducing $O(N)$ overhead at each switch.

## 8. Limitations Observed in This Implementation

Based on our recorded experiments, we observed the following operational and algorithmic limits:

1.  **Sacrifice of Optimality:** The modified priority function $f(n) = g(n) + h(n, goal) + h(n, target)$ readily accepts costlier paths if they satisfy the heuristic pull of a misleading waypoint, as demonstrated in Cases B, D, and G.
2.  **Sensitivity to Waypoint Sequence:** The algorithm is highly sensitive to the order of waypoints. Executing geometrically valid targets out of logical sequence dramatically increases node expansions (Case F).
3.  **Inference Latency:** Querying a local LLM API introduces substantial overhead (often $>10s$), which can eclipse the execution time of Standard A* on grids of this size.

## 9. Limitations of the Current Evaluation

The conclusions drawn above must be qualified by several methodological gaps:
1.  **Limited Environments:** The failure cases are small, handcrafted synthetic grids designed to stress-test specific mechanics. They do not represent average-case performance in broad, generalized environments.
2.  **Lack of Repeated LLM Trials:** Case E (Prompt Sensitivity) observed that an `exact` coordinate prompt yielded zero valid waypoints in a single run. Repeated statistical trials are required to reliably evaluate prompt effectiveness.
3.  **Scale:** The test sizes may not be large enough to definitively separate reprioritization overhead from OS timing jitter (Case I).

## 10. Conclusion and Future Work

This project implements a waypoint-guided A* search and a robust evaluation framework capable of independently verifying suboptimality using a Dijkstra baseline. 

Our failure-case benchmark demonstrates that while intermediate waypoints can alter search behaviour, the method's performance heavily depends on the geometric validity and sequential logic of those waypoints. Misleading or poorly ordered guidance can result in higher path costs and dramatically increased node expansions compared to unguided A*. Furthermore, LLM latency remains a significant bottleneck for the overall pipeline.

**Future Work:**
*   Conduct repeated statistical trials to evaluate LLM prompt representations accurately.
*   Expand testing to larger, randomized environments to measure generalized performance.
*   Explore admissible priority function variants that utilize waypoints without sacrificing optimal path guarantees.

## 11. Installation and Usage

### Prerequisites
*   Python 3.10+
*   [Ollama](https://ollama.ai/) running locally for LLM inference (using `qwen2.5:7b` by default).

### Commands

1.  **Run the Unit Test Suite**
    ```bash
    python -m unittest discover tests
    ```
2.  **Run a Standard End-to-End Experiment**
    ```bash
    python main.py
    ```
    *(Executes standard A*, queries the LLM, runs LLM-A*, compares metrics, and dumps artifacts into `results/`).*
3.  **Run the Failure-Case Benchmark**
    ```bash
    python run_failure_cases.py
    ```
    *(Executes Cases A-J against a Dijkstra baseline and generates `failure_results/FAILURE_REPORT.md`).*
4.  **Deterministic Replay**
    ```bash
    python main.py results/experiment_<uuid>.json
    ```
    *(Bypasses LLM inference and replays a cached scenario).*
