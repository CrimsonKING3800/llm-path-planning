"""
simulator.py

Grid-world multi-agent path planning simulator with independent validation
and matplotlib animation. This is the Stage B component from the spec.

The validator is hand-written (not LLM-generated) and independently verifies
the returned paths are legal — it does NOT trust the generated algorithm's
own claims of success.
"""

import traceback
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for headless operation
import matplotlib.pyplot as plt
import matplotlib.animation as animation


def _to_tuple(pos):
    """Convert a position (list or tuple) to a tuple for consistent comparison."""
    return tuple(pos)


def _to_tuple_list(positions):
    """Convert a list of positions to a list of tuples."""
    return [_to_tuple(p) for p in positions]


def validate_paths(paths, grid_size, starts, goals, obstacles, constraints=None):
    """
    Independent validator that checks generated paths for legality.

    This is a hand-written function that does NOT trust the generated
    algorithm's own claims — it independently verifies every path.

    Checks performed:
    - Each path starts at the correct start position
    - Each path ends at the correct goal position
    - Every position is within grid bounds
    - No position is on an obstacle
    - Each step is a valid 4-connected move (up/down/left/right) or wait
    - No vertex collisions (two agents in same cell at same timestep)
    - No edge/swap collisions (two agents swapping between timesteps)
    - For paths of different lengths, agents stay at their last position

    Args:
        paths: List of paths, where each path is a list of [x,y] or (x,y) positions.
        grid_size: [rows, cols] grid dimensions.
        starts: List of start positions per agent.
        goals: List of goal positions per agent.
        obstacles: List of obstacle positions.
        constraints: Optional constraints dict (used for movement type).

    Returns:
        Tuple (violations, illegal_moves).
    """
    violations = []
    illegal_moves = []

    # Get movement constraints
    movement_type = constraints.get("movement", "4-connected") if constraints else "4-connected"

    # Normalize all inputs to tuples for consistent comparison
    starts_t = _to_tuple_list(starts)
    goals_t = _to_tuple_list(goals)
    obstacles_set = set(_to_tuple_list(obstacles))
    rows, cols = grid_size[0], grid_size[1]

    if not paths:
        violations.append("No paths returned.")
        return violations, illegal_moves

    if len(paths) != len(starts_t):
        violations.append(
            f"Number of paths ({len(paths)}) does not match "
            f"number of agents ({len(starts_t)})."
        )
        return violations, illegal_moves

    # Normalize paths to tuples
    norm_paths = []
    for i, path in enumerate(paths):
        if not path:
            violations.append(f"Agent {i} has an empty path.")
            norm_paths.append([])
            continue
        norm_paths.append(_to_tuple_list(path))

    max_len = max(len(p) for p in norm_paths) if norm_paths else 0

    # --- Per-agent checks ---
    for i, path in enumerate(norm_paths):
        if not path:
            continue

        # Check start position
        if path[0] != starts_t[i]:
            violations.append(
                f"Agent {i} does not start at {starts_t[i]}, found {path[0]}."
            )

        # Check goal position
        if path[-1] != goals_t[i]:
            violations.append(
                f"Agent {i} does not end at goal {goals_t[i]}, found {path[-1]}."
            )

        for t, pos in enumerate(path):
            r, c = pos

            # Bounds check
            if r < 0 or r >= rows or c < 0 or c >= cols:
                violations.append(
                    f"Agent {i} out of bounds at step {t}: {pos} "
                    f"(grid is {rows}x{cols})."
                )

            # Obstacle check
            if pos in obstacles_set:
                violations.append(
                    f"Agent {i} on obstacle at step {t}: {pos}."
                )

            # Valid move check
            if t > 0:
                prev = path[t - 1]
                dr = abs(r - prev[0])
                dc = abs(c - prev[1])
                is_valid_move = False
                reason = ""
                
                if movement_type == "4-connected":
                    if (dr + dc) <= 1:
                        is_valid_move = True
                    else:
                        reason = f"moved by manhattan distance {dr + dc}, but 4-connected allows at most 1"
                elif movement_type == "8-connected":
                    if max(dr, dc) <= 1:
                        is_valid_move = True
                    else:
                        reason = f"moved by max distance max({dr}, {dc}), but 8-connected allows at most 1"
                else:
                    # Default to 4-connected if unknown
                    if (dr + dc) <= 1:
                        is_valid_move = True
                    else:
                        reason = f"unknown movement type {movement_type}, assumed 4-connected, got manhattan distance {dr + dc}"
                        
                if not is_valid_move:
                    illegal_moves.append({
                        "agent": i,
                        "step": t,
                        "from": prev,
                        "to": pos,
                        "reason": reason
                    })

    # --- Inter-agent collision checks ---
    for t in range(max_len):
        # Get positions at timestep t (agents past their path stay at goal)
        positions_t = []
        for i, path in enumerate(norm_paths):
            if not path:
                positions_t.append(None)
                continue
            pos = path[t] if t < len(path) else path[-1]
            positions_t.append(pos)

        # Vertex collisions: no two agents in the same cell
        seen = {}
        for i, pos in enumerate(positions_t):
            if pos is None:
                continue
            if pos in seen:
                violations.append(
                    f"Vertex collision: Agent {seen[pos]} and Agent {i} "
                    f"both at {pos} at step {t}."
                )
            else:
                seen[pos] = i

        # Edge/swap collisions: agents swapping positions
        if t > 0:
            positions_prev = []
            for i, path in enumerate(norm_paths):
                if not path:
                    positions_prev.append(None)
                    continue
                prev = path[t - 1] if (t - 1) < len(path) else path[-1]
                positions_prev.append(prev)

            for i in range(len(norm_paths)):
                for j in range(i + 1, len(norm_paths)):
                    if positions_t[i] is None or positions_t[j] is None:
                        continue
                    # Swap: i goes to where j was, j goes to where i was
                    if (positions_t[i] == positions_prev[j] and
                            positions_t[j] == positions_prev[i] and
                            positions_t[i] != positions_t[j]):
                        violations.append(
                            f"Swap collision: Agent {i} and Agent {j} "
                            f"swapped between step {t-1} and {t} "
                            f"({positions_prev[i]} <-> {positions_prev[j]})."
                        )

    return violations, illegal_moves


def run_simulation(plan_fn, grid_size, starts, goals, obstacles, constraints=None):
    """
    Runs the planning function and independently validates the output.

    This is the main simulator interface from Section 3.1 of the spec.

    Args:
        plan_fn: The generated planning function to evaluate.
        grid_size: [rows, cols] grid dimensions.
        starts: List of start positions per agent.
        goals: List of goal positions per agent.
        obstacles: List of obstacle positions.
        constraints: Optional constraints dict.

    Returns:
        Dict with keys: success, collisions, steps_per_agent, makespan,
        total_distance, paths, error.
    """
    if constraints is None:
        constraints = {}

    # Call the generated plan function
    try:
        paths = plan_fn(grid_size, starts, goals, obstacles, constraints)
    except Exception:
        return {
            "success": False,
            "collisions": [],
            "illegal_moves": [],
            "steps_per_agent": [],
            "makespan": 0,
            "total_distance": 0,
            "paths": [],
            "error": f"plan_fn raised an exception:\n{traceback.format_exc()}"
        }

    # Basic type check
    if not isinstance(paths, list):
        return {
            "success": False,
            "collisions": [],
            "illegal_moves": [],
            "steps_per_agent": [],
            "makespan": 0,
            "total_distance": 0,
            "paths": [],
            "error": f"plan_fn returned {type(paths).__name__}, expected list."
        }

    # Independent validation
    violations, illegal_moves = validate_paths(paths, grid_size, starts, goals, obstacles, constraints)

    # Compute metrics
    if paths and all(len(p) > 0 for p in paths):
        steps_per_agent = [len(p) - 1 for p in paths]
        makespan = max(steps_per_agent)
        total_distance = sum(steps_per_agent)
    else:
        steps_per_agent = []
        makespan = 0
        total_distance = 0

    return {
        "success": len(violations) == 0 and len(illegal_moves) == 0,
        "collisions": violations,
        "illegal_moves": illegal_moves,
        "steps_per_agent": steps_per_agent,
        "makespan": makespan,
        "total_distance": total_distance,
        "paths": paths,
        "error": None
    }


def animate_paths(paths, grid_size, obstacles, starts, goals, filename='animation.gif'):
    """
    Creates a matplotlib animation of agent paths on the grid.

    Draws the grid with obstacles, start/goal markers, and animates agents
    moving along their paths with colored markers and trailing lines.

    Args:
        paths: List of paths (each path is a list of (row, col) positions).
        grid_size: [rows, cols] grid dimensions.
        obstacles: List of obstacle positions.
        starts: List of start positions per agent.
        goals: List of goal positions per agent.
        filename: Output filename (default: 'animation.gif').
    """
    if not paths:
        print("No paths to animate.")
        return

    # Normalize to tuples
    norm_paths = [_to_tuple_list(p) for p in paths]
    starts_t = _to_tuple_list(starts)
    goals_t = _to_tuple_list(goals)
    obstacles_t = _to_tuple_list(obstacles)

    rows, cols = grid_size[0], grid_size[1]

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.set_xlim(-0.5, cols - 0.5)
    ax.set_ylim(-0.5, rows - 0.5)
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.set_title('Multi-Agent Path Planning Animation', fontsize=14)

    # Draw grid lines
    for x in range(cols + 1):
        ax.axvline(x - 0.5, color='lightgray', linewidth=0.5)
    for y in range(rows + 1):
        ax.axhline(y - 0.5, color='lightgray', linewidth=0.5)

    # Draw obstacles as dark squares
    for obs in obstacles_t:
        rect = plt.Rectangle(
            (obs[1] - 0.5, obs[0] - 0.5), 1, 1,
            facecolor='#2d2d2d', edgecolor='black', linewidth=1
        )
        ax.add_patch(rect)

    # Distinct colors for agents
    agent_colors = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
                    '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990']
    num_agents = len(norm_paths)

    # Draw start positions (circles) and goal positions (stars)
    for i in range(num_agents):
        color = agent_colors[i % len(agent_colors)]
        # Start marker
        ax.plot(starts_t[i][1], starts_t[i][0], 'o', markersize=10,
                color=color, markeredgecolor='black', markeredgewidth=1.5,
                zorder=5, label=f'Agent {i} start')
        # Goal marker
        ax.plot(goals_t[i][1], goals_t[i][0], '*', markersize=15,
                color=color, markeredgecolor='black', markeredgewidth=1,
                zorder=5)

    # Create line and point artists for animation
    trail_lines = []
    agent_markers = []
    for i in range(num_agents):
        color = agent_colors[i % len(agent_colors)]
        line, = ax.plot([], [], '-', color=color, alpha=0.4, linewidth=2)
        marker, = ax.plot([], [], 'o', markersize=12, color=color,
                          markeredgecolor='black', markeredgewidth=1.5, zorder=10)
        trail_lines.append(line)
        agent_markers.append(marker)

    max_len = max(len(p) for p in norm_paths) if norm_paths else 0
    step_text = ax.text(0.02, 0.98, '', transform=ax.transAxes,
                        fontsize=12, verticalalignment='top',
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    def init():
        for line in trail_lines:
            line.set_data([], [])
        for marker in agent_markers:
            marker.set_data([], [])
        step_text.set_text('')
        return trail_lines + agent_markers + [step_text]

    def update(frame):
        step_text.set_text(f'Step: {frame}')
        for i, path in enumerate(norm_paths):
            idx = min(frame, len(path) - 1)
            # Trail up to current position
            trail = path[:idx + 1]
            cols_trail = [p[1] for p in trail]
            rows_trail = [p[0] for p in trail]
            trail_lines[i].set_data(cols_trail, rows_trail)
            # Current position
            agent_markers[i].set_data([path[idx][1]], [path[idx][0]])
        return trail_lines + agent_markers + [step_text]

    ani = animation.FuncAnimation(
        fig, update, frames=max_len,
        init_func=init, blit=True, repeat=False, interval=500
    )

    try:
        from matplotlib.animation import PillowWriter
        ani.save(filename, writer=PillowWriter(fps=2))
        print(f"Animation saved to {filename}")
    except Exception as e:
        print(f"Could not save GIF (Pillow not available: {e}).")
        print("Saving static path overlay instead...")
        # Fall back to static plot
        for i, path in enumerate(norm_paths):
            if path:
                cols_path = [p[1] for p in path]
                rows_path = [p[0] for p in path]
                color = agent_colors[i % len(agent_colors)]
                ax.plot(cols_path, rows_path, '-', color=color,
                        alpha=0.6, linewidth=2)
        static_name = filename.rsplit('.', 1)[0] + '_static.png'
        plt.savefig(static_name, dpi=100, bbox_inches='tight')
        print(f"Static plot saved to {static_name}")

    plt.close(fig)


if __name__ == '__main__':
    # Simple test with a known-good 2-agent scenario
    def dummy_plan(grid_size, starts, goals, obstacles, constraints):
        """Hand-written valid paths for testing."""
        return [
            [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)],
            [(0, 2), (0, 1), (1, 1), (2, 1), (2, 2)],  # collision at (2,1) t=3 and (2,2) t=4
        ]

    grid = [3, 3]
    s = [[0, 0], [0, 2]]
    g = [[2, 2], [2, 2]]
    obs = [[1, 2]]

    print("Running simulation test...")
    result = run_simulation(dummy_plan, grid, s, g, obs)
    print(f"Success: {result['success']}")
    print(f"Makespan: {result['makespan']}")
    print(f"Total distance: {result['total_distance']}")
    if result['collisions']:
        print("Violations found:")
        for v in result['collisions']:
            print(f"  - {v}")
    else:
        print("No violations — paths are valid!")
