"""
run_poc.py

Main orchestrator for the LLM-driven multi-agent path planning PoC.
Wires together algorithm_gen.py (Stage A), simulator.py (Stage B),
and interpret.py (Stage C).

Runs the full pipeline N times (default 10, configurable via --runs),
logs per-run results to JSON files and a summary CSV, and generates
a matplotlib animation for the first successful run.

Usage:
    python run_poc.py --runs 10
"""

import argparse
import csv
import json
import logging
import multiprocessing
import os
import sys
import time

from algorithm_gen import (
    generate_algorithm_with_retry,
    inject_runtime_error_and_retry,
    inject_logic_error_and_retry,
    inject_illegal_move_error_and_retry,
)
from simulator import run_simulation, validate_paths, animate_paths
from interpret import interpret_results

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Hardcoded objective from Section 5 of the spec ---
OBJECTIVE = {
    "grid_size": [20, 20],
    "num_agents": 5,
    "starts": [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]],
    "goals": [[19, 19], [19, 18], [19, 17], [19, 16], [19, 15]],
    "obstacles": [[5, 5], [5, 6], [5, 7], [10, 10]],
    "constraints": {
        "avoid_agent_collisions": True,
        "max_steps": 100,
        "movement": "4-connected"
    },
    "objective": "minimize_makespan"
}

# Maximum total LLM attempts (generation + runtime corrections) per run
MAX_ATTEMPTS = 3
MODEL = "qwen2.5:7b"


def _run_plan_in_worker(code_str, objective, result_queue):
    """
    Worker function that runs in a separate process.
    Executes the generated code, extracts the plan function, runs simulation,
    and puts the result into the queue.

    Using a separate process provides:
    - Timeout protection against infinite loops
    - Isolation so a crash doesn't kill the main pipeline

    The queue receives either:
      {"sim_results": ..., "code_ran": True}
    or:
      {"error": "<message>", "traceback": "<tb>", "code_ran": False}
    """
    import traceback as _tb
    try:
        # Execute generated code in a restricted namespace
        namespace = {'__builtins__': __builtins__}
        exec(code_str, namespace)

        plan_fn = namespace.get('plan')
        if not callable(plan_fn):
            result_queue.put({
                "error": "Generated code did not define a callable 'plan' function.",
                "traceback": "",
                "code_ran": False
            })
            return

        # Convert list-based positions to tuples for the generated code.
        # The prompt says "(x,y) coordinates" (tuples), but the JSON objective
        # uses lists. LLM-generated code invariably tries to use positions as
        # dict keys (for A* visited sets etc.), which requires hashable tuples.
        grid_size = tuple(objective["grid_size"])
        starts_t = [tuple(s) for s in objective["starts"]]
        goals_t = [tuple(g) for g in objective["goals"]]
        obstacles_t = [tuple(o) for o in objective["obstacles"]]
        constraints = objective["constraints"]

        # Run the simulation with the generated plan function
        sim_results = run_simulation(
            plan_fn=plan_fn,
            grid_size=grid_size,
            starts=starts_t,
            goals=goals_t,
            obstacles=obstacles_t,
            constraints=constraints
        )

        # Convert paths to serializable format (lists of lists)
        if sim_results.get("paths"):
            sim_results["paths"] = [
                [list(pos) for pos in path]
                for path in sim_results["paths"]
            ]

        result_queue.put({"sim_results": sim_results, "code_ran": True})

    except Exception as e:
        result_queue.put({
            "error": f"Execution error: {e}",
            "traceback": _tb.format_exc(),
            "code_ran": False
        })


def _execute_code_with_timeout(code_str, objective, timeout=10):
    """
    Run generated code in a subprocess with a timeout.

    Returns:
        (worker_result_dict, timed_out: bool)
        worker_result_dict has keys: code_ran, error, traceback (optional), sim_results (optional)
    """
    result_queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=_run_plan_in_worker,
        args=(code_str, objective, result_queue)
    )
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        return {"error": f"Timed out after {timeout}s", "traceback": "", "code_ran": False}, True

    if result_queue.empty():
        return {"error": "Worker produced no output", "traceback": "", "code_ran": False}, False

    return result_queue.get(), False


def _evaluate_sim_result(sim_results, objective):
    """
    Extract metrics from a simulation result dict.

    Returns a dict with: collision_free, all_goals_reached, num_collisions,
    collisions (raw list), makespan, total_distance, paths, unreached_agents.
    """
    collisions = sim_results.get("collisions", [])
    illegal_moves = sim_results.get("illegal_moves", [])
    num_collisions = len(collisions)
    collision_free = (num_collisions == 0)
    makespan = sim_results.get("makespan", 0)
    total_distance = sim_results.get("total_distance", 0)
    paths = sim_results.get("paths", [])

    # Check if all agents reached their goals
    goals_t = [tuple(g) for g in objective["goals"]]
    all_goals_reached = True
    unreached_agents = []
    if paths:
        for i, path in enumerate(paths):
            if not path or tuple(path[-1]) != goals_t[i]:
                all_goals_reached = False
                unreached_agents.append({
                    "agent_index": i,
                    "goal": goals_t[i],
                    "final_pos": tuple(path[-1]) if path else None,
                })
    else:
        all_goals_reached = False

    return {
        "collision_free": collision_free,
        "all_goals_reached": all_goals_reached,
        "num_collisions": num_collisions,
        "collisions": collisions,
        "illegal_moves": illegal_moves,
        "makespan": makespan,
        "total_distance": total_distance,
        "paths": paths,
        "unreached_agents": unreached_agents,
    }


def _is_better_result(candidate, current_best):
    """
    Returns True if candidate is a better partial result than current_best.
    Fewer collisions wins first; then more goals reached wins.
    """
    if current_best is None:
        return True
    if candidate["num_collisions"] < current_best["num_collisions"]:
        return True
    if candidate["num_collisions"] == current_best["num_collisions"]:
        if candidate["all_goals_reached"] and not current_best["all_goals_reached"]:
            return True
    return False


def run_single(objective, run_id):
    """
    Runs a single iteration of the full pipeline:
    1. Generate algorithm (LLM call) — with self-correction retry loop (up to MAX_ATTEMPTS)
    2. Execute + simulate (in subprocess with timeout)
       - Crashes, timeouts, AND logically wrong results (collisions/unreached goals)
         all trigger correction retries within the same MAX_ATTEMPTS budget.
    3. Interpret results (LLM call)

    Tracks the best partial result across all attempts so that if the run
    ultimately fails, we report the best metrics achieved, not the last.

    Args:
        objective: The structured objective dict.
        run_id: Integer identifier for this run.

    Returns:
        Dict with run results including metrics, interpretation, and attempts_used.
    """
    logger.info(f"=== Run {run_id} ===")
    attempts_used = 0

    # --- Stage A: Algorithm Generation (attempt 1, static-validation retry built in) ---
    logger.info(f"  [A] Generating algorithm via LLM ({MODEL})...")
    try:
        code_str, gen_attempts = generate_algorithm_with_retry(
            objective, model=MODEL, max_attempts=MAX_ATTEMPTS
        )
        attempts_used = gen_attempts
        logger.info(
            f"  [A] Algorithm generated successfully "
            f"({len(code_str)} chars, static attempts: {gen_attempts})"
        )
    except ValueError as e:
        attempts_used = MAX_ATTEMPTS
        logger.warning(f"  [A] Code validation failed after {MAX_ATTEMPTS} attempts: {e}")
        return _make_failure_result(run_id, f"Algorithm validation: {e}", attempts_used)
    except Exception as e:
        attempts_used = MAX_ATTEMPTS
        logger.error(f"  [A] Algorithm generation failed: {e}")
        return _make_failure_result(run_id, f"Algorithm generation: {e}", attempts_used)

    # --- Stage B: Simulation loop (runtime + logic self-correction) ---
    logger.info(f"  [B] Running simulation (10s timeout)...")

    max_exec_attempts = MAX_ATTEMPTS  # up to 3 plan() runs
    exec_attempt_num = 0              # how many plan() runs we've done this run
    current_code = code_str
    best_result = None                # best partial result across all attempts
    final_success = False             # True if any attempt is fully correct
    final_sim_results = None          # sim_results for the final/best attempt
    attempt_history = []              # list of dicts summarizing each attempt

    while exec_attempt_num < max_exec_attempts:
        exec_attempt_num += 1
        worker_result, timed_out = _execute_code_with_timeout(current_code, objective, timeout=10)

        # --- Check for crash/timeout failure ---
        run_error: str | None = None
        if timed_out:
            run_error = "Timed out after 10s (infinite loop or very slow algorithm)"
        elif not worker_result.get("code_ran"):
            err = worker_result.get("error", "Unknown error")
            tb = worker_result.get("traceback", "")
            run_error = f"{err}\n{tb}".strip() if tb else err
        else:
            sr = worker_result.get("sim_results", {})
            if sr.get("error"):
                run_error = sr["error"]

        if run_error is not None:
            # ---- Crash/timeout failure path ----
            short_err = run_error.split("\n")[0][:120]
            logger.warning(
                f"  [B] Execution attempt {exec_attempt_num}/{max_exec_attempts} "
                f"crashed: {short_err}"
            )

            if exec_attempt_num >= max_exec_attempts:
                attempt_history.append({
                    "attempt": exec_attempt_num,
                    "code": current_code,
                    "result_type": "crash",
                    "collisions": None,
                    "goals_reached": None,
                    "error_summary": short_err
                })
                break  # exhausted — will return best result below

            logger.info(
                f"  [B] Requesting runtime correction "
                f"(execution {exec_attempt_num} → {exec_attempt_num + 1})..."
            )
            try:
                attempt_history.append({
                    "attempt": exec_attempt_num,
                    "code": current_code,
                    "result_type": "crash",
                    "collisions": None,
                    "goals_reached": None,
                    "error_summary": short_err
                })
                current_code, _ = inject_runtime_error_and_retry(
                    objective,
                    failing_code=current_code,
                    runtime_error=run_error,
                    model=MODEL,
                    max_remaining_attempts=1,
                )
                logger.info(f"  [B] Correction received — will retry execution.")
            except ValueError as e:
                logger.warning(f"  [B] Correction generation failed: {e}")
                break  # can't correct further — will return best result below
            continue

        # --- Code ran without crashing — evaluate the result ---
        sim_results = worker_result["sim_results"]
        eval_result = _evaluate_sim_result(sim_results, objective)

        # Convert paths to serializable format
        if sim_results.get("paths"):
            sim_results["paths"] = [
                [list(pos) for pos in path]
                for path in sim_results["paths"]
            ]
            eval_result["paths"] = sim_results["paths"]

        # Track best partial result
        if _is_better_result(eval_result, best_result):
            best_result = eval_result
            final_sim_results = sim_results

        logger.info(
            f"  [B] Attempt {exec_attempt_num}/{max_exec_attempts}: "
            f"Collisions: {eval_result['num_collisions']} | "
            f"Goals reached: {eval_result['all_goals_reached']} | "
            f"Makespan: {eval_result['makespan']}"
        )

        if eval_result["collision_free"] and eval_result["all_goals_reached"] and not eval_result.get("illegal_moves"):
            # Fully correct — stop retrying
            final_success = True
            attempt_history.append({
                "attempt": exec_attempt_num,
                "code": current_code,
                "result_type": "success",
                "collisions": eval_result["num_collisions"],
                "goals_reached": eval_result["all_goals_reached"],
                "error_summary": None
            })
            break

        # ---- Logic failure path: ran but wrong ----
        if exec_attempt_num >= max_exec_attempts:
            logger.warning(
                f"  [B] All {max_exec_attempts} execution attempts exhausted "
                f"(best: {best_result['num_collisions']} collisions). "
                f"Marking run as failed."
            )
            attempt_history.append({
                "attempt": exec_attempt_num,
                "code": current_code,
                "result_type": "logic_error" if not eval_result.get("illegal_moves") else "illegal_move",
                "collisions": eval_result["num_collisions"],
                "goals_reached": eval_result["all_goals_reached"],
                "error_summary": "Exhausted attempts"
            })
            break

        # Trigger illegal move correction if there are illegal moves, otherwise general logic correction
        if eval_result.get("illegal_moves"):
            logger.info(
                f"  [B] Illegal moves detected — requesting movement logic correction "
                f"(execution {exec_attempt_num} → {exec_attempt_num + 1})..."
            )
            try:
                attempt_history.append({
                    "attempt": exec_attempt_num,
                    "code": current_code,
                    "result_type": "illegal_move",
                    "collisions": eval_result["num_collisions"],
                    "goals_reached": eval_result["all_goals_reached"],
                    "error_summary": f"Found {len(eval_result['illegal_moves'])} illegal moves"
                })
                current_code, _ = inject_illegal_move_error_and_retry(
                    objective,
                    failing_code=current_code,
                    illegal_moves=eval_result["illegal_moves"],
                    model=MODEL,
                    max_remaining_attempts=1,
                )
                logger.info(f"  [B] Movement correction received — will retry execution.")
            except ValueError as e:
                logger.warning(f"  [B] Movement correction generation failed: {e}")
                break
        else:
            logger.info(
                f"  [B] Logic error detected — requesting correction "
                f"(execution {exec_attempt_num} → {exec_attempt_num + 1})..."
            )
            try:
                attempt_history.append({
                    "attempt": exec_attempt_num,
                    "code": current_code,
                    "result_type": "logic_error",
                    "collisions": eval_result["num_collisions"],
                    "goals_reached": eval_result["all_goals_reached"],
                    "error_summary": "Collisions or unreached goals"
                })
                current_code, _ = inject_logic_error_and_retry(
                    objective,
                    failing_code=current_code,
                    collision_details=eval_result["collisions"],
                    all_goals_reached=eval_result["all_goals_reached"],
                    unreached_agents=eval_result["unreached_agents"],
                    makespan=eval_result["makespan"],
                    total_distance=eval_result["total_distance"],
                    model=MODEL,
                    max_remaining_attempts=1,
                )
                logger.info(f"  [B] Logic correction received — will retry execution.")
            except ValueError as e:
                logger.warning(f"  [B] Logic correction generation failed: {e}")
                break

    attempts_used = exec_attempt_num

    # --- Determine final outcome ---
    if best_result is None:
        # No attempt ever ran successfully (all crashed/timed out)
        return _make_failure_result(run_id, "All attempts crashed or timed out", attempts_used, attempt_history=attempt_history)

    collision_free = best_result["collision_free"]
    all_goals_reached = best_result["all_goals_reached"]
    num_collisions = best_result["num_collisions"]
    makespan = best_result["makespan"]
    total_distance = best_result["total_distance"]
    paths = best_result["paths"]

    status = "SUCCESS" if final_success else "FAILED"
    logger.info(
        f"  [B] Final result: {status} | "
        f"Collisions: {num_collisions} | "
        f"Makespan: {makespan} | "
        f"Total dist: {total_distance} | "
        f"Attempts: {attempts_used}"
    )

    # --- Stage C: Interpretation ---
    logger.info(f"  [C] Interpreting results via LLM...")
    try:
        interpretation = interpret_results(objective, final_sim_results)
        logger.info(f"  [C] Interpretation received ({len(interpretation)} chars)")
    except Exception as e:
        logger.warning(f"  [C] Interpretation failed: {e}")
        interpretation = f"Interpretation failed: {e}"

    return {
        "run_id": run_id,
        "model_used": MODEL,
        "code_ran": True,
        "collision_free": collision_free,
        "all_goals_reached": all_goals_reached,
        "makespan": makespan,
        "total_distance": total_distance,
        "num_collisions": num_collisions,
        "attempts_used": attempts_used,
        "best_attempt_collisions": num_collisions,
        "best_attempt_goals_reached": all_goals_reached,
        "error": None if final_success else f"Logic errors remain after {attempts_used} attempts",
        "interpretation": interpretation,
        "attempt_history": attempt_history,
        "paths": paths
    }


def _make_failure_result(run_id, error_msg, attempts_used=1,
                         best_attempt_collisions=None,
                         best_attempt_goals_reached=None,
                         attempt_history=None):
    """Helper to create a standardized failure result dict."""
    return {
        "run_id": run_id,
        "model_used": MODEL,
        "code_ran": False,
        "collision_free": False,
        "all_goals_reached": False,
        "makespan": None,
        "total_distance": None,
        "num_collisions": 0,
        "attempts_used": attempts_used,
        "best_attempt_collisions": best_attempt_collisions,
        "best_attempt_goals_reached": best_attempt_goals_reached,
        "error": error_msg,
        "interpretation": "Pipeline did not reach interpretation stage.",
        "attempt_history": attempt_history or [],
        "paths": []
    }


def write_summary_csv(all_results, csv_path):
    """Write the per-run results summary to a CSV file."""
    fieldnames = [
        "run_id", "model", "code_ran", "collision_free", "all_goals_reached",
        "makespan", "total_distance", "num_collisions", "attempts_used",
        "best_attempt_collisions", "best_attempt_goals_reached", "error"
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for res in all_results:
            # Map model_used to model column for CSV
            row = {k: res.get(k, "") for k in fieldnames}
            row["model"] = res.get("model_used", "")
            # Truncate error to first line for CSV cleanliness
            # Full errors are in the per-run JSON files
            if row.get("error"):
                row["error"] = str(row["error"]).split('\n')[0][:200]
            writer.writerow(row)


def print_summary(all_results, num_runs):
    """Print a formatted summary table to stdout."""
    code_ran_count = sum(1 for r in all_results if r["code_ran"])
    collision_free_count = sum(1 for r in all_results if r["collision_free"])
    goals_reached_count = sum(1 for r in all_results if r["all_goals_reached"])
    full_success_count = sum(
        1 for r in all_results
        if r["code_ran"] and r["collision_free"] and r["all_goals_reached"]
    )

    successful = [
        r for r in all_results
        if r["code_ran"] and r["collision_free"] and r["all_goals_reached"]
    ]
    avg_makespan = (
        sum(r["makespan"] for r in successful) / len(successful)
        if successful else 0
    )
    avg_distance = (
        sum(r["total_distance"] for r in successful) / len(successful)
        if successful else 0
    )
    avg_attempts = (
        sum(r.get("attempts_used", 1) for r in all_results) / len(all_results)
        if all_results else 0
    )

    print("\n" + "=" * 55)
    print("          MULTI-AGENT PATH PLANNING PoC — SUMMARY")
    print("=" * 55)
    print(f"  Total runs:                    {num_runs}")
    print(f"  Code execution success rate:   {code_ran_count}/{num_runs} "
          f"({code_ran_count / num_runs * 100:.1f}%)")
    print(f"  Collision-free rate:           {collision_free_count}/{num_runs} "
          f"({collision_free_count / num_runs * 100:.1f}%)")
    print(f"  All goals reached rate:        {goals_reached_count}/{num_runs} "
          f"({goals_reached_count / num_runs * 100:.1f}%)")
    print(f"  Full success rate:             {full_success_count}/{num_runs} "
          f"({full_success_count / num_runs * 100:.1f}%)")
    print(f"  Avg makespan (successes):      {avg_makespan:.1f}")
    print(f"  Avg total distance (successes): {avg_distance:.1f}")
    print(f"  Avg attempts per run:          {avg_attempts:.2f}")
    print("=" * 55)


def main():
    """Main entry point: parse args, run pipeline N times, report results."""
    parser = argparse.ArgumentParser(
        description="LLM-Driven Multi-Agent Path Planning PoC"
    )
    parser.add_argument(
        "--runs", type=int, default=10,
        help="Number of pipeline runs (default: 10)"
    )
    args = parser.parse_args()
    num_runs = args.runs

    # Create results directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    print(f"\nStarting {num_runs} pipeline runs...\n")
    all_results = []
    first_success = None

    for i in range(1, num_runs + 1):
        result = run_single(OBJECTIVE, i)
        all_results.append(result)

        # Save per-run JSON (exclude paths to keep files manageable)
        json_result = {k: v for k, v in result.items() if k != "paths"}
        json_path = os.path.join(results_dir, f"run_{i}.json")
        with open(json_path, "w") as f:
            json.dump(json_result, f, indent=2)

        # Track first fully successful run for animation
        is_full_success = (
            result["code_ran"] and
            result["collision_free"] and
            result["all_goals_reached"]
        )
        if is_full_success and first_success is None:
            first_success = result
            logger.info(f"  >>> First fully successful run: #{i}")

        print()  # Blank line between runs

    # --- Write summary CSV ---
    csv_path = os.path.join(base_dir, "results_summary.csv")
    write_summary_csv(all_results, csv_path)
    logger.info(f"Summary CSV written to {csv_path}")

    # --- Print summary ---
    print_summary(all_results, num_runs)

    # --- Animate first successful run ---
    if first_success:
        anim_path = os.path.join(base_dir, "first_success_animation.gif")
        logger.info(f"Animating successful run #{first_success['run_id']}...")
        try:
            animate_paths(
                paths=first_success["paths"],
                grid_size=OBJECTIVE["grid_size"],
                obstacles=OBJECTIVE["obstacles"],
                starts=OBJECTIVE["starts"],
                goals=OBJECTIVE["goals"],
                filename=anim_path
            )
        except Exception as e:
            logger.error(f"Animation failed: {e}")
    else:
        logger.warning("No fully successful run to animate.")

    print(f"\nDone. Results saved to: {csv_path}")


if __name__ == "__main__":
    multiprocessing.freeze_support()  # Required for Windows
    main()
