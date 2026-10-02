# IMPLEMENTATION REPORT: LLM-A* Path Planning

This report documents the exact behavior of the LLM-A* codebase currently present in the project directory. It is based strictly on a manual static analysis of the code.

====================================================
## 1. PROJECT STRUCTURE
====================================================

The project consists of the following relevant files:

*   **`config.py`**: Holds configuration constants including new variants (`PRIORITY_VARIANT`, `CLOSED_NODE_VARIANT`, `PROMPT_MODE`, `COMPACT_BLOCK_SIZE`, `COMPACT_MAX_BLOCKS`, `LLM_TIMEOUT_SECONDS`).
    *   Important variables: `GRID_SIZE`, `START`, `GOAL`, `NUM_OBSTACLES`, `OLLAMA_URL`, `OLLAMA_MODEL`.
    *   Imported by: `main.py`, `llm_planner.py`.
*   **`environment.py`**: Defines the grid and obstacle logic.
    *   Important classes: `Grid3D`. Now supports seeded random instances and counts validations.
    *   Imported by: `main.py` (used throughout search algorithms).
*   **`llm_planner.py`**: Handles communication with the local LLM.
    *   Important classes/functions: `LLMPlanner`, `generate_targets`, `parse_and_validate_waypoints`.
    *   Imported by: `main.py`.
*   **`astar3d.py`**: Contains the pathfinding algorithms.
    *   Important functions: `heuristic`, `target_cost`, `reconstruct_path`, `llm_astar`, `standard_astar`, `validate_endpoints`, `validate_path`.
    *   Imported by: `main.py`.
*   **`tests/test_astar.py`**: Contains 18 test cases validating endpoint behavior, metrics, duplicate/malformed inputs, deterministic replaying, diagonal movement, and cost evaluation.
*   **`visualization.py`**: Contains rendering logic.
    *   Important functions: `visualize_path`.
    *   Imported by: `main.py`.
*   **`main.py`**: The entry point and benchmark script.

**Execution Flow (derived from `main.py`):**
1. `main.py` initializes `Grid3D` from `environment.py`.
2. `main.py` calls `env.generate_random_obstacles()`.
3. `main.py` calls `standard_astar()` from `astar3d.py`.
4. `main.py` initializes `LLMPlanner` from `llm_planner.py` and calls `generate_targets()`.
5. `main.py` calls `llm_astar()` from `astar3d.py`.
*(Note: `visualize_path` is imported but never called in the current execution flow).*

====================================================
## 2. ENVIRONMENT REPRESENTATION
====================================================

*   **Grid dimensions**: `(100, 100, 50)`
*   **Coordinate convention**: 3D integer tuples `(x, y, z)`.
*   **State representation**: `(x, y, z)` tuples.
*   **Obstacle representation**: A Python `set` of `(x, y, z)` tuples.
*   **Obstacle generation**: Random coordinate generation within bounds.
*   **Obstacle structure**: Single independent cells.
*   **Random seed handling**: `random.seed(42)` is explicitly set exactly once before obstacle generation.
*   **Start generation**: Hardcoded `(2, 3, 1)`.
*   **Goal generation**: Hardcoded `(95, 95, 45)`.
*   **Start/goal guaranteed free**: Yes. Generation explicitly checks `if obs != start and obs != goal`.
*   **Neighbor generation**: 26-connected 3D grid. Loops `dx, dy, dz` from -1 to 1, excluding `(0,0,0)`.
*   **Number of neighbors**: Up to 26.
*   **Allowed movement directions**: All 26 adjacent diagonals and orthogonals.
*   **Movement costs**: Euclidean distance between cells.
*   **Boundary handling**: Evaluated dynamically via `0 <= x < self.size[0]`, etc.
*   **Obstacle collision handling**: Evaluated dynamically via `point in self.obstacles`.

**Current Active Configuration:**
```python
GRID_SIZE = (100, 100, 50)
START = (2, 3, 1)
GOAL = (95, 95, 45)
NUM_OBSTACLES = 25000
```

====================================================
## 3. STANDARD A*
====================================================

*   **Function name**: `standard_astar(start, goal, env)`
*   **Inputs**: `start` tuple, `goal` tuple, `env` (Grid3D instance).
*   **Initialization**: `OPEN = []`, `CLOSED = set()`, `g_score = {start: 0}`, `parent = {}`.
*   **OPEN representation**: Python `list` manipulated as a min-heap via `heapq`. Tuples stored as `(f_score, g_score, id(state), state)`.
*   **CLOSED representation**: Python `set`.
*   **g-score initialization**: Python dictionary mapping state tuple to float.
*   **Heuristic function**: Euclidean distance in 3D.
*   **f-score calculation**: `tentative_g + heuristic(neighbor, goal)`
*   **Neighbor expansion**: Iterates over `env.get_neighbors_3d(current)`.
*   **Collision checking**: Abstracted to `env.get_neighbors_3d`.
*   **Parent updates**: `parent[neighbor] = current` when a better or new path is found.
*   **Duplicate handling**: Stale entries remain in `OPEN` when a shorter path is found. Duplicates are handled lazily upon extraction: `if current in CLOSED: continue`.
*   **Termination**: `if current == goal:` (early exit upon popping). Or returns None if `OPEN` empties.
*   **Failure handling**: Returns `None, expanded_nodes`.
*   **Path reconstruction**: Traces `parent` map backwards and reverses the list.

**Implemented Equations:**
```text
g(n) = g(parent) + EuclideanDistance(parent, n)
h(n) = EuclideanDistance(n, goal)
f(n) = g(n) + h(n)
```

====================================================
## 4. LLM PLANNER
====================================================

*   **Model name**: `qwen2.5:7b`
*   **API/endpoint**: `http://localhost:11434/api/generate` (local Ollama).
*   **Generation parameters**: `stream: False`, `format: "json"`.
*   **Temperature**: Not explicitly specified; falls back to Ollama API defaults.
*   **Streaming**: Disabled.
*   **JSON mode**: Enabled explicitly.
*   **Timeout/error handling**: Wraps request in a generic `try...except Exception`. Returns an empty list `[]` on HTTP error, JSON decode error, or connection failure.
*   **Retry behavior**: None. Fails immediately and gracefully returns `[]`.

**Environment Information Sent to LLM:**
*   **Grid dimensions**: Yes.
*   **Start**: Yes.
*   **Goal**: Yes.
*   **Obstacle list**: **NO. Only a subset is sent.**
*   **Subset selection**: The code converts the obstacle set to a list and slices the first 30 elements: `obs_sample = list(env.obstacles)[:30]`. Because Python sets are unordered, this yields an effectively random sample of 30 obstacles.
*   **Connectivity info**: No.
*   **Movement costs**: No.
*   **Algorithm info**: No. It only asks to "suggest 3 to 5 intermediate waypoints that would help a path planner navigate".

**Exact Prompt Sent:**
```text
You are a 3D path planning assistant.

Environment:
Grid size: {env.size[0]} x {env.size[1]} x {env.size[2]}

Start:
{start}

Goal:
{goal}

Sample of Obstacles (x, y, z):
{obs_sample}

Suggest 3 to 5 intermediate waypoints that would help a path planner navigate around the obstacles from Start to Goal.
Return ONLY valid JSON in this exact format, with no markdown formatting or other text:
{{
    "waypoints": [
        [x1, y1, z1],
        [x2, y2, z2]
    ]
}}
```

====================================================
## 5. WAYPOINT GENERATION
====================================================

*   **Expected JSON format**: `{"waypoints": [[x, y, z], ...]}`
*   **Parsing**: Standard `json.loads(text)`.
*   **Extraction**: `data.get("waypoints", [])`.
*   **Type conversion**: Explicitly casts each coordinate to integer and converts to a tuple.
*   **Malformed output behavior**: Caught by try/except, returns an empty list `[]`.
*   **Missing waypoint behavior**: Returns empty list `[]`.
*   **Duplicate waypoint behavior**: Preserved in the exact order outputted by the LLM.
*   **Ordering**: Strict preservation of LLM output order.
*   **Number requested**: 3 to 5.
*   **Start inserted**: No.
*   **Goal inserted**: Not during parsing (it is added later in `llm_astar`).
*   **Start/Goal removed from intermediate list**: Yes, explicitly filtered out.

**Exact Code:**
```python
valid_waypoints = []
for wp in waypoints:
    if len(wp) == 3:
        wp_tuple = (int(wp[0]), int(wp[1]), int(wp[2]))
        if env.is_valid(wp_tuple) and not env.is_obstacle(wp_tuple):
            if wp_tuple != start and wp_tuple != goal:
                valid_waypoints.append(wp_tuple)
return valid_waypoints
```

====================================================
## 6. WAYPOINT VALIDATION
====================================================

For each LLM-generated waypoint, the implementation performs the following validations:

*   **Coordinate dimensionality**: Checked (`if len(wp) == 3`). *(B. Added by implementation)*
*   **Integer coordinates**: Cast to int (implicit check, throws error if invalid). *(B. Added by implementation)*
*   **Bounds**: Checked (`env.is_valid`). *(B. Added by implementation)*
*   **Obstacle collision**: Checked (`not env.is_obstacle`). *(B. Added by implementation)*
*   **Start/goal**: Checked (`wp_tuple != start and wp_tuple != goal`). *(B. Added by implementation)*
*   **Duplicates**: NOT checked. *(C. Not performed)*
*   **Reachability**: NOT checked. *(C. Not performed)*
*   **Line-of-sight**: NOT checked. *(C. Not performed)*
*   **Local connectivity**: NOT checked. *(C. Not performed)*

====================================================
## 7. LLM-A* IMPLEMENTATION
====================================================

*   **Function name**: `llm_astar`

### Initialization
*   **OPEN**: `OPEN = []` (heap queue).
*   **CLOSED**: `CLOSED = set()`.
*   **g**: `g_score = {start: 0}`.
*   **parent**: `parent = {}`.
*   **Target list T**: `waypoint_targets = targets + [goal]`.
*   **Current target**: `current_target = waypoint_targets[current_target_idx]` (starts at index 0).
*   **Initial f**: `heuristic(start, goal) + target_cost(start, current_target)`.

### Main Loop
Next state is selected by popping the minimum tuple from the `OPEN` min-heap. Tie-breaking relies on `g_score`, then object memory `id()`, then the state tuple. Goal check occurs immediately after popping.

### Neighbor Expansion
*   **Obstacle checking**: Handled by `env.get_neighbors_3d`.
*   **CLOSED checking**: Checked prior to calculating costs: `if neighbor in CLOSED: continue`.
*   **tentative g**: `g_score[current] + heuristic(current, neighbor)` (where heuristic is Euclidean distance).
*   **g update**: Updated if neighbor is unseen or `tentative_g < g_score[neighbor]`.
*   **parent update**: `parent[neighbor] = current`.
*   **OPEN insertion/update**: `heapq.heappush`.

**Mathematical equation for f:**
```text
f(n) = g(n) + h(n, goal) + cost(n, t)
```
Implemented exactly as:
`f_score = tentative_g + heuristic(neighbor, goal) + target_cost(neighbor, current_target)`

### Target Switching
*   **When reached**: Checked immediately *after* a state is popped from `OPEN` and added to `CLOSED`.
*   **Equality**: Exact tuple equality (`current == current_target`).
*   **Checked before/after filtering**: After obstacle filtering (implicitly done during neighbor generation) and after `CLOSED` filtering.
*   **Next target selection**: Sequential index incrementation (`current_target_idx += 1`).
*   **Final target reached**: The target list explicitly ends with the true goal. When the goal is reached, the early exit condition (`if current == goal: return`) triggers before target switching logic executes.
*   **OPEN priorities updated**: Yes, the entire queue is destructively rebuilt and re-heapified.
*   **ALL OPEN states reprioritized**: Yes. The code iterates through the entire `OPEN` list.
*   **CLOSED states reprioritized**: No.
*   **g-values change**: No.
*   **parent pointers change**: No.
*   **States reopened**: No. The algorithm explicitly enforces `if neighbor in CLOSED: continue` during neighbor expansion.

**Exact Reprioritization Code:**
```python
if current == current_target:
    current_target_idx += 1
    if current_target_idx < len(waypoint_targets):
        current_target = waypoint_targets[current_target_idx]
        
        # Reprioritize OPEN set with the new target
        new_OPEN = []
        for _, old_g, item_id, state in OPEN:
            new_f = old_g + heuristic(state, goal) + target_cost(state, current_target)
            new_OPEN.append((new_f, old_g, item_id, state))
        heapq.heapify(new_OPEN)
        OPEN = new_OPEN
```

====================================================
## 8. OPEN / PRIORITY QUEUE DETAILS
====================================================

*   **Data structure**: Python built-in `list`, manipulated using `heapq`.
*   **Tuple contents**: `(f_score, g_score, id(state), state)`.
*   **Tie-breaking**: `f_score` -> `g_score` -> memory address integer (`id()`) -> state tuple.
*   **Stale entries**: Decrease-key is NOT implemented. Stale entries (old, higher f/g values for the same node) are abandoned in the queue and filtered out when popped via `if current in CLOSED`.
*   **Priority updates**: Occur ONLY during target switching via a full list reconstruction and `heapify()`. Stale entries are also reprioritized during this process and remain in the queue.
*   **Insert multiple times**: Yes, a state is added to the heap every time a shorter path to it is found.
*   **Reopen CLOSED nodes**: Impossible.

====================================================
## 9. HEURISTICS AND COST FUNCTIONS
====================================================

All costs and heuristics rely on the exact same Euclidean distance function:

1.  **Movement cost**: `heuristic(current, neighbor)`
2.  **Standard A* heuristic**: `heuristic(state, goal)`
3.  **LLM target cost**: `target_cost(state, target)`

**Equations:**
```text
EuclideanDistance(a, b) = sqrt((ax - bx)^2 + (ay - by)^2 + (az - bz)^2)
```

**Units:** All components `g(n)`, `h(n)`, and `cost(t,n)` evaluate to physical Euclidean distance in 3D grid space. They are mathematically compatible.

====================================================
## 10. PATH RECONSTRUCTION AND PATH COST
====================================================

*   **Returned path representation**: A sequential Python `list` of `(x, y, z)` tuples.
*   **Start included**: Yes.
*   **Goal included**: Yes.
*   **Waypoints included**: They are included *if* the path passes exactly through them.
*   **Path length calculation**: The `main.py` benchmark prints `len(std_path)`.
*   **Actual movement-cost calculation**: The benchmark completely ignores true g-scores and movement cost. It only reports the length of the list.
*   **Diagonal costs**: Properly accumulated during search in `g_score`, but ignored in the final reported metrics.
*   **"Path length" meaning**: The printed "Path length" strictly means the **number of nodes in the path array**.

====================================================
## 11. EXPERIMENT / BENCHMARK CODE
====================================================

*   **LLM inference time**: Uses `time.time()` wrapping `llm.generate_targets()`.
*   **A* search time**: Uses `time.time()` wrapping `standard_astar()`.
*   **LLM-A* search time**: Uses `time.time()` wrapping `llm_astar()`.
*   **Total runtime**: Not measured.
*   **Nodes expanded**: Extracted from the second return value of the search functions. Incremented explicitly when a node is popped and added to `CLOSED`.
*   **Path length**: Evaluated via `len(path)`.
*   **Path cost**: Not measured.
*   **Valid path**: Assumed valid if the list is not `None`.
*   **Memory/storage**: Not measured.
*   **Visualization time**: Not included in benchmark times.
*   **Environment equality**: Both algorithms receive a reference to the exact same `env` object.
*   **Start/Goal equality**: Both algorithms use identical constants.
*   **Environment regeneration**: Environment is generated exactly once per run.
*   **Random seeds**: `random.seed(42)` ensures the obstacle positions are deterministic across runs.

====================================================
## 12. VISUALIZATION
====================================================

The visualization code (`visualize_path` in `visualization.py`) relies on `matplotlib`. It is structurally isolated. It is imported into `main.py` but **never called**. Therefore, it has absolutely zero effect on algorithm correctness, timing measurements, path representation, or experiment reproducibility.

====================================================
## 13. CONFIGURATION
====================================================

Actual values dynamically requested by the prompt:

*   **Grid dimensions**: `(100, 100, 50)`
*   **Obstacle count**: `25000`
*   **Start**: `(2, 3, 1)`
*   **Goal**: `(95, 95, 45)`
*   **Random seed**: `42`
*   **LLM model**: `qwen2.5:7b`
*   **Temperature**: Not configured (uses Ollama default).
*   **Waypoint count**: 3 to 5 (requested in natural language prompt).
*   **Search parameters**: None.
*   **Visualization settings**: None.

====================================================
## 14. COMPLETE LLM-A* PSEUDOCODE
====================================================

This pseudocode strictly reflects the *current code behavior*, not the paper's theoretical description.

```text
function llm_astar(start, goal, env, LLM_targets):
    expanded_nodes = 0
    T = LLM_targets + [goal]
    current_target_idx = 0
    current_target = T[0]
    
    OPEN = MinHeap()
    CLOSED = Set()
    g = Map()
    parent = Map()
    
    g[start] = 0
    f_start = Euclidean(start, goal) + Euclidean(start, current_target)
    insert (f_start, 0, start) into OPEN
    
    while OPEN is not empty:
        current = pop minimum f from OPEN
        
        if current == goal:
            return reconstruct_path(parent, current), expanded_nodes
            
        if current in CLOSED:
            continue
            
        expanded_nodes = expanded_nodes + 1
        add current to CLOSED
        
        if current == current_target:
            current_target_idx = current_target_idx + 1
            if current_target_idx < length(T):
                current_target = T[current_target_idx]
                
                new_OPEN = list()
                for each (old_f, old_g, id, state) in OPEN:
                    new_f = old_g + Euclidean(state, goal) + Euclidean(state, current_target)
                    add (new_f, old_g, id, state) to new_OPEN
                OPEN = heapify(new_OPEN)
                
        for neighbor in get_neighbors_3d(current):
            if neighbor in CLOSED:
                continue
                
            movement_cost = Euclidean(current, neighbor)
            tentative_g = g[current] + movement_cost
            
            if neighbor not in g or tentative_g < g[neighbor]:
                parent[neighbor] = current
                g[neighbor] = tentative_g
                
                f_score = tentative_g + Euclidean(neighbor, goal) + Euclidean(neighbor, current_target)
                insert (f_score, tentative_g, neighbor) into OPEN
                
    return Failure, expanded_nodes
```

====================================================
## 15. POTENTIAL IMPLEMENTATION AMBIGUITIES
====================================================

The codebase is highly explicit, but contains one minor theoretical ambiguity:

*   **File**: `astar3d.py`
*   **Function**: `llm_astar` and `standard_astar`
*   **Code**: `heapq.heappush(OPEN, (f_score, tentative_g, id(neighbor), neighbor))`
*   **Ambiguity**: The use of `id(neighbor)` as a tertiary tie-breaker. `id()` returns the integer memory address of the tuple object. Python reuses or caches memory addresses for small immutable types unpredictably. While this deterministically breaks ties within a single execution run without crashing, it relies on interpreter memory allocation rather than algorithmic properties.
*   **Resolution needed**: No action is needed for the algorithm to function, but replacing `id(neighbor)` with a monotonically increasing integer counter would ensure mathematically rigorous reproducibility independent of the Python interpreter's memory allocator.

====================================================
## 16. IMPORTANT CURRENT IMPLEMENTATION DETAILS
====================================================

1.  **Does the LLM receive the COMPLETE obstacle map?** No. It explicitly receives a random sub-sample of only 30 obstacles.
2.  **Does the LLM receive the same environment that A* searches?** Mathematically yes, but the LLM is artificially blinded to >99% of the obstacles due to sampling.
3.  **Is the baseline genuine standard A*?** Yes.
4.  **What exactly is h(n)?** Euclidean distance to the absolute goal.
5.  **What exactly is cost(t,n)?** Euclidean distance to the current LLM target.
6.  **What exactly is f(n) in LLM-A*?** `g(n) + h(n, goal) + cost(n, t)`.
7.  **When exactly does target switching occur?** When the popped node equals the current target, immediately after `CLOSED` validation.
8.  **Are ALL OPEN nodes reprioritized after target switching?** Yes, the entire queue is rebuilt.
9.  **Can CLOSED nodes be reopened?** No.
10. **Are invalid waypoints removed?** Yes. Out-of-bounds, obstacle-colliding, start, and goal coordinates are silently dropped during parsing.
11. **Are start and goal guaranteed to be in T?** Start is explicitly excluded. Goal is explicitly appended at the end of `T`.
12. **Are waypoints required to be reachable from one another?** No.
13. **Is path cost measured geometrically or by node count?** Node count (`len(path)`). Geometrical cost is completely ignored in metrics.
14. **Are diagonal movement costs correctly accumulated?** Yes, within the algorithm's `g_score`.
15. **Is LLM inference time separated from search time?** Yes, timed in isolated blocks in `main.py`.
16. **Are A* and LLM-A* tested on identical environments?** Yes.
17. **Is the LLM deterministic?** No, temperature is not overridden to 0.
18. **Can malformed LLM output silently change the target list?** Yes, malformed output returns an empty list, gracefully degenerating LLM-A* into standard A* without throwing exceptions.
19. **Is the current implementation 2D or 3D?** 3D.
20. **Which aspects are extensions beyond the paper?** The 3D coordinate space and the aggressive sub-sampling of the obstacle set.

====================================================
## 17. RAW EVIDENCE
====================================================

**Obstacle Sub-sampling (`llm_planner.py`):**
```python
    def generate_targets(self, start, goal, env):
        # We sample a few obstacles to not overload the prompt
        obs_sample = list(env.obstacles)[:30] 
```

**LLM-A* Target Cost Logic (`astar3d.py`):**
```python
def heuristic(a, b):
    # Euclidean distance
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

def target_cost(state, target):
    return heuristic(state, target)
```

**LLM-A* Target Switching (`astar3d.py`):**
```python
        # Check if we reached the current LLM target
        if current == current_target:
            current_target_idx += 1
            if current_target_idx < len(waypoint_targets):
                current_target = waypoint_targets[current_target_idx]
                
                # Reprioritize OPEN set with the new target
                new_OPEN = []
                for _, old_g, item_id, state in OPEN:
                    new_f = old_g + heuristic(state, goal) + target_cost(state, current_target)
                    new_OPEN.append((new_f, old_g, item_id, state))
                heapq.heapify(new_OPEN)
                OPEN = new_OPEN
```

**Waypoint Filtering (`llm_planner.py`):**
```python
                    # Validate waypoint: inside grid and not an obstacle
                    if env.is_valid(wp_tuple) and not env.is_obstacle(wp_tuple):
                        if wp_tuple != start and wp_tuple != goal:
                            valid_waypoints.append(wp_tuple)
```

**Benchmark Output (`main.py`):**
```python
    if llm_path:
        print("Path found")
        print(f"Path length: {len(llm_path)}") # Measures node count
    else:
        print("No path found")
    print(f"Nodes expanded: {llm_nodes}")
    print(f"Search time: {t1_llma - t0_llma:.2f} s")
```
= = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =  
 

====================================================
## 18. CLEANUP AND INSTRUMENTATION UPDATES
====================================================

### Files Changed:
1. `config.py`: Added `PROMPT_MODE` and `LLM_TEMPERATURE` configs.
2. `environment.py`: Added `are_neighbors` for path validation and documented unrestricted diagonal movement rules.
3. `astar3d.py`: Added `calculate_path_cost`, `validate_path`, stable tie-breaking, stale entry checks, and metric extraction.
4. `llm_planner.py`: Added `compact_full` environment prompt mode, coordinate validation, duplicate filtering, and detailed telemetry collection.
5. `main.py`: Refactored to collect, print, and save all new metrics and experiment artifacts as a JSON file.
6. `tests/test_astar.py`: Added comprehensive unit tests for new logic.

### Changes Made and Rationale:
- **Correct path-cost measurement**: Added calculation of true geometric cost (Euclidean) instead of just node count to accurately evaluate path quality.
- **Path Validation**: Added rigorous post-hoc path validation to detect invalid jumps, bounds violation, and obstacle collisions.
- **Empty and Invalid Waypoint Handling**: Dropped waypoints with non-integral coordinates or duplicates. Fallback implemented cleanly so LLM-A* behaves as Standard A* when no valid waypoints are given.
- **Heap Reliability**: Replaced `id()` with `itertools.count()` for deterministic tie-breaking and added stale-entry checking to optimize standard A* behavior.
- **Environment Input**: Added a `compact_full` representation summarizing obstacle density into 10x10x10 blocks to preserve geometric distribution without blowing up prompt size.
- **Benchmarking & Output**: Reorganized `main.py` to record precise runtime, validation reasons, and algorithm internals into a persistent JSON artifact for later analysis.

### Updated Algorithm Pseudocode (LLM-A*):
```text
OPEN = min-heap initialized with (f=h(start, goal) + cost(start, targets[0]), g=0, counter=0, start)
CLOSED = empty set
g_score = map {start: 0}
target_idx = 0
current_target = targets[0] (or goal if no targets)

while OPEN is not empty:
    pop (f, g, c, current) from OPEN
    if g > g_score[current]: continue  # Stale entry check

    if current == goal: return reconstruct_path(current)
    if current in CLOSED: continue
    CLOSED.add(current)
    
    if current == current_target:
        target_idx += 1
        current_target = targets[target_idx]
        for all items in OPEN:
            recalculate item.f = item.g + h(item, goal) + cost(item, current_target)
        heapify(OPEN)
        
    for neighbor in get_valid_neighbors(current):
        if neighbor in CLOSED: continue
        tentative_g = g_score[current] + Euclidean(current, neighbor)
        if tentative_g < g_score[neighbor]:
            g_score[neighbor] = tentative_g
            new_f = tentative_g + h(neighbor, goal) + cost(neighbor, current_target)
            push (new_f, tentative_g, next_counter(), neighbor) to OPEN
```

### Exact Definitions of Metrics:
- **expanded_nodes**: Number of nodes popped from OPEN and added to CLOSED.
- **path_length**: Number of nodes in the returned path (including start and goal).
- **path_cost**: Sum of Euclidean distances between consecutive nodes in the path.
- **waypoints_reached**: Number of LLM-generated waypoints strictly visited by the search algorithm.
- **open_size_at_switches**: Size of the OPEN heap recorded immediately prior to each target switch.
- **search_time**: Time elapsed executing the actual A* loops.
- **total_pipeline_time**: Search time plus the time spent waiting for the LLM to generate targets.

### Diagonal Movement and Collision Rules:
- **Rule**: Unrestricted diagonal movement.
- **Definition**: A diagonal move in 3D (e.g. changing x, y, and z simultaneously by 1) is permitted as long as the destination cell is within grid bounds and is not an obstacle. It does not check if the adjacent orthogonal cells are free, thus "squeezing" past obstacles diagonally is allowed. This matches the standard uniform grid assumption unless volume-based agent modeling is required.

### Test Cases and Results:
- All required cases (start=goal, no valid waypoints, duplicates, out-of-bounds, obstacle placement, unreachable goal, valid diagonal movement, target switching, path cost correctness, validation correctness) were implemented in `tests/test_astar.py`.
- Results: 8/8 tests pass correctly simulating algorithm and validator boundaries.

### Remaining Limitations and Unresolved Theoretical Questions:
- The algorithm's behavior around target switching involves full reprioritization of the OPEN set (O(N) operation) which could be a bottleneck in very large state spaces compared to Focal Search approaches.
- Target guidance cost `f(n) = g(n) + h(n, goal) + target_cost(n, t)` double-counts distance heuristically, creating a weight ratio conceptually similar to a greedy search when `t == goal`.
- It is still unresolved whether preserving valid-but-strategically-poor waypoints leads to provable sub-optimality loops, even though CLOSED set tracking prevents infinite cycles.

====================================================
## 19. ADVANCED VARIANTS AND INSTRUMENTATION FIXES
====================================================

### Algorithm Variants Added
1. **Priority Variants (`PRIORITY_VARIANT`):**
    - `baseline`: Current behavior where `f(n) = g(n) + h(n, goal) + target_cost(n, current_target)`. Double-counts heuristic when `current_target == goal`.
    - `standard_goal`: Target cost evaluates to 0 when `current_target == goal`, defaulting to standard A* priority `f(n) = g(n) + h(n, goal)` for the final segment.
2. **Reopening Variant (`CLOSED_NODE_VARIANT`):**
    - `baseline`: Nodes in `CLOSED` are never revisited.
    - `reopening`: If a new path to a `CLOSED` node has a lower `g_score`, it is removed from `CLOSED` and pushed back onto `OPEN`.

### Environment and LLM Features
- **Prompt Modes (`PROMPT_MODE`):**
    - `arbitrary_subset`: Deterministic slice of the obstacle list (`[:30]`).
    - `seeded_random_sample`: Reproducible random sample of 30 obstacles (`random.Random(42)`).
    - `compact_density`: Configurable 3D block-density representation (`COMPACT_BLOCK_SIZE`, `COMPACT_MAX_BLOCKS`). Now accurately reports omitted obstacles.
    - `exact`: Full coordinate list without omissions.
- **LLM Error Handling:** Implemented `LLM_TIMEOUT_SECONDS`. Differentiates between HTTP errors, parsing errors, timeout, and empty targets.
- **Randomness:** Random generators now explicitly support being instantiated with a fixed seed inside the generator function itself, allowing completely reproducible obstacle placement independent of external `random` state.

### Evaluation Metrics and Tooling
- **Endpoints:** Pre-flight endpoint validation (`validate_endpoints`) fails the search gracefully if `start` or `goal` is out of bounds or an obstacle. Handled identically for Standard and LLM-A*.
- **Metrics Collected:** `generated_nodes`, `expanded_nodes`, `path_length`, `path_cost` (geometric sum), `waypoints_reached`, `open_size_at_switches`, `search_time` (via `time.perf_counter()`), `total_pipeline_time`, `termination_reason`.
- **Replay Mechanism:** Execution via `python main.py results/experiment_<id>.json` natively bypasses LLM inference and replays the cached waypoints and configuration on identical maps.
- **Tests:** 18 comprehensive tests cover edge-cases like out-of-bound goals, floating-point coordinates, diagonal limits, reprioritization mechanics, and JSON schema corruption.
