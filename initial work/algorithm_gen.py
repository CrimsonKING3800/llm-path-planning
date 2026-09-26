import ast
import re
from typing import Dict, Any, Optional, Tuple

import requests

def _call_ollama(prompt: str, model: str = "qwen2.5:7b", timeout: int = 60) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2048
        }
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to communicate with Ollama: {e}")
        print("Please ensure Ollama is running (`ollama serve`).")
        raise SystemExit(1)

# ---------------------------------------------------------------------------
# Section 2.2 — tightened generation prompt
# ---------------------------------------------------------------------------
PROMPT_TEMPLATE = """\
You are designing a multi-agent path planning algorithm.

Given:
- A grid of size {grid_size}  (a Python tuple (width, height))
- {num_agents} agents with start positions {starts} and goal positions {goals}
- Static obstacles at {obstacles}
- Constraints: {constraints}
- Objective: {objective}

=== CRITICAL RULES — READ CAREFULLY ===

1. TUPLES ONLY.  All coordinates are Python **tuples** (x, y), not lists.
   - CORRECT:  pos = (x + 1, y)
   - WRONG:    pos = [x + 1, y]
   Never use a list as a dictionary key or in a set — only tuples are hashable.

2. grid_size IS A TUPLE (width, height).  Access dimensions like this:
   - width, height = grid_size
   Do NOT treat grid_size as an integer or index it as grid_size[0] without unpacking.

3. WORKED EXAMPLE of correct coordinate handling:
   # Expand neighbours in 4-connected grid
   for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
       nx, ny = x + dx, y + dy
       neighbour = (nx, ny)   # <-- always a tuple
       if neighbour not in obstacles_set:   # obstacles_set is a set of tuples
           ...

4. NO CODE AFTER THE FUNCTION.  Return only the function definition (plus any
   helper functions or imports it needs).  Do NOT add:
   - test calls such as  plan(...)
   - if __name__ == '__main__':  blocks
   - example usage, print statements, or assertions outside the function body.

5. KEEP IT SIMPLE AND CORRECT.  A basic BFS or priority-queue (A*) approach
   with proper collision avoidance is strongly preferred over a clever but
   brittle algorithm.  Correctness beats performance.

=== FUNCTION SIGNATURE ===

Write a single Python function:

    def plan(grid_size, starts, goals, obstacles, constraints) -> list:

The function must:
  a. Return a list of paths — one per agent — where each path is a list of
     (x, y) tuples from start to goal (inclusive of both endpoints).
  b. Avoid all static obstacles (given as a list of tuples).
  c. Avoid inter-agent collisions at every timestep (no two agents in the
     same cell at the same time, and no two agents swapping positions).
  d. Use only the Python standard library (no external packages).
  e. Be entirely self-contained.

Return ONLY the function code (and any helpers / imports it needs), no explanation.\
"""

# ---------------------------------------------------------------------------
# Correction prompt — sent when the generated code fails
# ---------------------------------------------------------------------------
CORRECTION_TEMPLATE = """\
The following Python function was generated for a multi-agent path planning task,
but it produced an error when executed.

=== ORIGINAL OBJECTIVE ===
{objective_summary}

=== CODE THAT FAILED ===
```python
{failing_code}
```

=== ERROR PRODUCED ===
{error_message}

=== YOUR TASK ===
Fix ONLY the bug described above.  Return the corrected, complete function
(including any helper functions it needs) and nothing else — no explanation,
no test calls, no if __name__ == '__main__' block.

Remember the critical rules:
- All coordinates must be tuples (x, y), never lists.
- grid_size is a tuple (width, height).
- Do not include any code outside the function definition(s).\
"""

# ---------------------------------------------------------------------------
# Logic-error correction prompt — sent when code runs but produces wrong results
# ---------------------------------------------------------------------------
LOGIC_CORRECTION_TEMPLATE = """\
The following Python function was generated for a multi-agent path planning task.
It runs without crashing, but produces **logically incorrect** results.

=== ORIGINAL OBJECTIVE ===
{objective_summary}

=== CODE THAT PRODUCED WRONG RESULTS ===
```python
{failing_code}
```

=== WHAT WENT WRONG ===

Collisions detected: {num_collisions}
{collision_details}

All agents reached goals: {all_goals_reached}
{unreached_details}

Makespan: {makespan} steps
Total distance: {total_distance}

=== YOUR TASK ===
The code above runs fine but has a **logic bug** in the collision-avoidance or
path-planning logic.  Identify the specific flaw causing the violations listed
above and fix it.  Do NOT regenerate from scratch — edit the existing code.

Return the corrected, complete function (including any helper functions it needs)
and nothing else — no explanation, no test calls, no if __name__ == '__main__' block.

Remember the critical rules:
- All coordinates must be tuples (x, y), never lists.
- grid_size is a tuple (width, height).
- Do not include any code outside the function definition(s).\
"""

# ---------------------------------------------------------------------------
# Illegal-move correction prompt — sent when code produces moves that violate movement rules
# ---------------------------------------------------------------------------
ILLEGAL_MOVE_CORRECTION_TEMPLATE = """\
The following Python function was generated for a multi-agent path planning task.
It runs without crashing, but it produced **illegal moves** that violate the
movement constraints.

=== ORIGINAL OBJECTIVE ===
{objective_summary}

=== CODE THAT PRODUCED ILLEGAL MOVES ===
```python
{failing_code}
```

=== WHAT WENT WRONG ===
Your plan() function produced an illegal move: {illegal_move_details}

Valid moves from any position (x,y) are ONLY:
{valid_moves_explanation}

=== YOUR TASK ===
The code above has a basic bug in how it generates or selects moves. Fix the
movement generation logic so it only ever produces the exact valid moves listed above.
Do NOT regenerate from scratch — edit the existing code.

Return the corrected, complete function (including any helper functions it needs)
and nothing else — no explanation, no test calls, no if __name__ == '__main__' block.

Remember the critical rules:
- All coordinates must be tuples (x, y), never lists.
- grid_size is a tuple (width, height).
- Do not include any code outside the function definition(s).\
"""

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_and_clean_code(generated_text: str) -> str:
    """
    Extract code from markdown fences (if present) and strip trailing
    test/usage code that the LLM often appends.

    Returns the cleaned code string.
    Raises ValueError on parse failure or missing 'plan' function.
    """
    # Extract from ```python ... ``` or ``` ... ``` fences
    match = re.search(r'```(?:python)?(.*?)```', generated_text, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1).strip()
    else:
        code = generated_text.strip()

    # Validate syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Generated code has syntax errors: {e}\n\nCode:\n{code}")

    # Validate that a 'plan' function is defined
    has_plan = any(
        isinstance(node, ast.FunctionDef) and node.name == 'plan'
        for node in ast.walk(tree)
    )
    if not has_plan:
        raise ValueError("Generated code does not define a 'plan' function.")

    # Strip trailing test/usage code — keep only imports, defs, classes, assignments.
    clean_nodes = [
        node for node in tree.body
        if isinstance(node, (
            ast.Import, ast.ImportFrom,
            ast.FunctionDef, ast.AsyncFunctionDef,
            ast.ClassDef, ast.Assign,
        ))
        # Skip if-name-main and bare Expr (function calls like plan(...), print(...))
    ]

    clean_tree = ast.Module(body=clean_nodes, type_ignores=[])
    return ast.unparse(clean_tree)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_algorithm(objective: Dict[str, Any], model: str = None) -> str:
    """
    Generate a multi-agent path planning algorithm using the configured LLM backend.

    Args:
        objective: Dict with keys: grid_size, num_agents, starts, goals,
                   obstacles, constraints, objective.
        model: Ollama model name (default: "llama3.2").

    Returns:
        Cleaned Python code string defining the `plan` function.

    Raises:
        SystemExit: If the Ollama server is unreachable.
        ValueError: If the generated code cannot be validated after generation.
    """
    prompt = PROMPT_TEMPLATE.format(**objective)
    raw = _call_ollama(prompt, model=model)
    return _extract_and_clean_code(raw)


def generate_algorithm_with_retry(
    objective: Dict[str, Any],
    model: str = None,
    max_attempts: int = 3,
) -> Tuple[str, int]:
    """
    Generate a multi-agent path planning algorithm with a self-correction retry loop.

    On the first attempt the full generation prompt is used.  If static
    validation fails (syntax error or missing plan function), a correction prompt
    is sent with the failing code + exact error, asking the LLM to fix only the bug.

    For runtime/timeout errors the caller should use inject_runtime_error_and_retry.

    Args:
        objective: Dict with keys: grid_size, num_agents, starts, goals,
                   obstacles, constraints, objective.
        model: Ollama model name.
        max_attempts: Maximum number of generation+validation attempts.

    Returns:
        Tuple (code_str, attempts_used).

    Raises:
        ValueError: If all attempts are exhausted without valid code.
        SystemExit: If the Ollama server is unreachable.
    """
    last_error: Optional[str] = None
    last_code: Optional[str] = None
    raw: str = ""

    for attempt in range(1, max_attempts + 1):
        if attempt == 1 or last_code is None:
            prompt = PROMPT_TEMPLATE.format(**objective)
        else:
            objective_summary = (
                f"Grid: {objective['grid_size']}, "
                f"Agents: {objective['num_agents']}, "
                f"Starts: {objective['starts']}, "
                f"Goals: {objective['goals']}, "
                f"Obstacles: {objective['obstacles']}, "
                f"Objective: {objective['objective']}"
            )
            prompt = CORRECTION_TEMPLATE.format(
                objective_summary=objective_summary,
                failing_code=last_code,
                error_message=last_error,
            )

        try:
            raw = _call_ollama(prompt, model=model)
            code = _extract_and_clean_code(raw)
            return code, attempt
        except ValueError as e:
            last_error = str(e)
            # Recover whatever code we have for the correction prompt
            m = re.search(r'```(?:python)?(.*?)```', raw, re.DOTALL | re.IGNORECASE)
            last_code = m.group(1).strip() if m else raw.strip()

    raise ValueError(
        f"Failed to generate valid code after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )


def inject_runtime_error_and_retry(
    objective: Dict[str, Any],
    failing_code: str,
    runtime_error: str,
    model: str = None,
    max_remaining_attempts: int = 2,
) -> Tuple[str, int]:
    """
    Given a runtime error from a previously generated code string, ask the LLM
    to correct it and return (new_code, extra_attempts_used).

    Args:
        objective: The original planning objective dict.
        failing_code: The code string that caused the runtime error.
        runtime_error: The exact error message / traceback to feed back.
        model: Ollama model name.
        max_remaining_attempts: How many more correction attempts are allowed.

    Returns:
        Tuple (corrected_code_str, extra_attempts_used).

    Raises:
        ValueError: If correction fails within the allowed attempts.
        SystemExit: If the Ollama server is unreachable.
    """
    last_code = failing_code
    last_error = runtime_error
    raw: str = ""

    for attempt in range(1, max_remaining_attempts + 1):
        objective_summary = (
            f"Grid: {objective['grid_size']}, "
            f"Agents: {objective['num_agents']}, "
            f"Starts: {objective['starts']}, "
            f"Goals: {objective['goals']}, "
            f"Obstacles: {objective['obstacles']}, "
            f"Objective: {objective['objective']}"
        )
        prompt = CORRECTION_TEMPLATE.format(
            objective_summary=objective_summary,
            failing_code=last_code,
            error_message=last_error,
        )

        try:
            raw = _call_ollama(prompt, model=model)
            code = _extract_and_clean_code(raw)
            return code, attempt
        except ValueError as e:
            last_error = str(e)
            m = re.search(r'```(?:python)?(.*?)```', raw, re.DOTALL | re.IGNORECASE)
            last_code = m.group(1).strip() if m else raw.strip()

    raise ValueError(
        f"Correction failed after {max_remaining_attempts} extra attempts. "
        f"Last error: {last_error}"
    )

def inject_logic_error_and_retry(
    objective: Dict[str, Any],
    failing_code: str,
    collision_details: list,
    all_goals_reached: bool,
    unreached_agents: list,
    makespan: int,
    total_distance: int,
    model: str = None,
    max_remaining_attempts: int = 1,
) -> Tuple[str, int]:
    """
    Given code that ran without crashing but produced logically wrong results
    (collisions or unreached goals), ask the LLM to correct the logic bug.

    Args:
        objective: The original planning objective dict.
        failing_code: The code string that produced wrong results.
        collision_details: List of violation strings from the validator.
        all_goals_reached: Whether all agents reached their goals.
        unreached_agents: List of dicts with keys: agent_index, goal, final_pos.
        makespan: The makespan of the failed attempt.
        total_distance: The total distance of the failed attempt.
        model: Ollama model name.
        max_remaining_attempts: How many more correction attempts are allowed.

    Returns:
        Tuple (corrected_code_str, extra_attempts_used).

    Raises:
        ValueError: If correction fails within the allowed attempts.
        SystemExit: If the Ollama server is unreachable.
    """
    last_code = failing_code
    raw: str = ""

    # Format collision details — show up to 3 specific violations
    num_collisions = len(collision_details)
    if collision_details:
        shown = collision_details[:3]
        collision_text = "Specific violations (first {n}):\n".format(
            n=min(3, num_collisions)
        )
        for v in shown:
            collision_text += f"  - {v}\n"
        if num_collisions > 3:
            collision_text += f"  ... and {num_collisions - 3} more.\n"
    else:
        collision_text = "No collisions detected."

    # Format unreached-goals details
    if not all_goals_reached and unreached_agents:
        unreached_text = "Agents that did NOT reach their goals:\n"
        for info in unreached_agents:
            unreached_text += (
                f"  - Agent {info['agent_index']}: "
                f"goal={info['goal']}, ended at {info['final_pos']}\n"
            )
    elif all_goals_reached:
        unreached_text = "All agents reached their goals."
    else:
        unreached_text = "Goal-reach status could not be determined."

    objective_summary = (
        f"Grid: {objective['grid_size']}, "
        f"Agents: {objective['num_agents']}, "
        f"Starts: {objective['starts']}, "
        f"Goals: {objective['goals']}, "
        f"Obstacles: {objective['obstacles']}, "
        f"Objective: {objective['objective']}"
    )

    for attempt in range(1, max_remaining_attempts + 1):
        prompt = LOGIC_CORRECTION_TEMPLATE.format(
            objective_summary=objective_summary,
            failing_code=last_code,
            num_collisions=num_collisions,
            collision_details=collision_text,
            all_goals_reached=all_goals_reached,
            unreached_details=unreached_text,
            makespan=makespan,
            total_distance=total_distance,
        )

        try:
            raw = _call_ollama(prompt, model=model)
            code = _extract_and_clean_code(raw)
            return code, attempt
        except ValueError as e:
            last_error = str(e)
            m = re.search(r'```(?:python)?(.*?)```', raw, re.DOTALL | re.IGNORECASE)
            last_code = m.group(1).strip() if m else raw.strip()

    raise ValueError(
        f"Logic correction failed after {max_remaining_attempts} extra attempts. "
        f"Last error: {last_error}"
    )


def inject_illegal_move_error_and_retry(
    objective: Dict[str, Any],
    failing_code: str,
    illegal_moves: list,
    model: str = None,
    max_remaining_attempts: int = 1,
) -> Tuple[str, int]:
    """
    Given code that ran but produced illegal moves, ask the LLM to correct the movement logic.

    Args:
        objective: The original planning objective dict.
        failing_code: The code string that produced wrong results.
        illegal_moves: List of dicts describing illegal moves.
        model: Ollama model name.
        max_remaining_attempts: How many more correction attempts are allowed.

    Returns:
        Tuple (corrected_code_str, extra_attempts_used).

    Raises:
        ValueError: If correction fails within the allowed attempts.
    """
    last_code = failing_code
    raw: str = ""

    # Just show the first illegal move to keep it focused
    if not illegal_moves:
        raise ValueError("inject_illegal_move_error_and_retry called but illegal_moves is empty")
        
    first_move = illegal_moves[0]
    illegal_move_details = (
        f"agent {first_move['agent']} moved from {first_move['from']} "
        f"to {first_move['to']} at step {first_move['step']}, which is not "
        f"a valid move. Reason: {first_move['reason']}"
    )

    movement_type = objective.get("constraints", {}).get("movement", "4-connected")
    if movement_type == "4-connected":
        valid_moves_explanation = (
            "- (x+1, y) [down]\n"
            "- (x-1, y) [up]\n"
            "- (x, y+1) [right]\n"
            "- (x, y-1) [left]\n"
            "- (x, y) [stay in place]"
        )
    elif movement_type == "8-connected":
        valid_moves_explanation = (
            "- (x+1, y) [down]\n"
            "- (x-1, y) [up]\n"
            "- (x, y+1) [right]\n"
            "- (x, y-1) [left]\n"
            "- (x+1, y+1) [down-right]\n"
            "- (x-1, y-1) [up-left]\n"
            "- (x+1, y-1) [down-left]\n"
            "- (x-1, y+1) [up-right]\n"
            "- (x, y) [stay in place]"
        )
    else:
        valid_moves_explanation = f"Matches the '{movement_type}' constraint."

    objective_summary = (
        f"Grid: {objective['grid_size']}, "
        f"Agents: {objective['num_agents']}, "
        f"Starts: {objective['starts']}, "
        f"Goals: {objective['goals']}, "
        f"Obstacles: {objective['obstacles']}, "
        f"Constraints: {objective.get('constraints', {})}, "
        f"Objective: {objective['objective']}"
    )

    for attempt in range(1, max_remaining_attempts + 1):
        prompt = ILLEGAL_MOVE_CORRECTION_TEMPLATE.format(
            objective_summary=objective_summary,
            failing_code=last_code,
            illegal_move_details=illegal_move_details,
            valid_moves_explanation=valid_moves_explanation,
        )

        try:
            raw = _call_ollama(prompt, model=model)
            code = _extract_and_clean_code(raw)
            return code, attempt
        except ValueError as e:
            last_error = str(e)
            m = re.search(r'```(?:python)?(.*?)```', raw, re.DOTALL | re.IGNORECASE)
            last_code = m.group(1).strip() if m else raw.strip()

    raise ValueError(
        f"Illegal move correction failed after {max_remaining_attempts} extra attempts. "
        f"Last error: {last_error}"
    )

# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_objective = {
        "grid_size": [20, 20],
        "num_agents": 5,
        "starts": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]],
        "goals": [[19, 19], [19, 18], [19, 17], [19, 16], [19, 15]],
        "obstacles": [[5, 5], [5, 6], [5, 7], [10, 10]],
        "constraints": {
            "avoid_agent_collisions": True,
            "max_steps": 100,
            "movement": "4-connected",
        },
        "objective": "minimize_makespan",
    }

    print("Requesting algorithm generation from Ollama (qwen2.5:7b)...")
    try:
        code, attempts = generate_algorithm_with_retry(sample_objective, model="qwen2.5:7b")
        print(f"\nGenerated Code Successfully Parsed! (attempts: {attempts})\n")
        print("-" * 50)
        print(code)
        print("-" * 50)
    except Exception as e:
        print(f"Error: {e}")
