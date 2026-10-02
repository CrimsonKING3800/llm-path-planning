import time
import random
import json
import uuid
import os
import sys
from datetime import datetime
import config as cfg
from environment import Grid3D
from llm_planner import LLMPlanner
from astar3d import llm_astar, standard_astar, validate_path
from visualization import visualize_path

def run_experiment(replay_data=None):
    if replay_data:
        print(f"Replaying experiment: {replay_data['run_id']}")
        run_id = f"replay_{replay_data['run_id']}"
        seed = replay_data["seed"]
        c = replay_data["config"]
        grid_size = tuple(c["GRID_SIZE"])
        start = tuple(c["START"])
        goal = tuple(c["GOAL"])
        num_obstacles = c["NUM_OBSTACLES"]
        obstacles_list = [tuple(obs) for obs in replay_data["obstacles"]]
        
        env = Grid3D(grid_size)
        env.obstacles = set(obstacles_list)
        
        # Override config variants if we want to test different algorithms on the same map
        # Or we can just use the config imported
        prompt_mode = c["PROMPT_MODE"]
        llm_waypoints = [tuple(wp) for wp in replay_data["llm"].get("waypoints", [])]
        llm_info = replay_data["llm"]
        inference_time = llm_info.get("inference_time", 0.0)
    else:
        run_id = str(uuid.uuid4())
        seed = 42
        print(f"Run ID: {run_id}")
        grid_size = cfg.GRID_SIZE
        start = cfg.START
        goal = cfg.GOAL
        num_obstacles = cfg.NUM_OBSTACLES
        prompt_mode = cfg.PROMPT_MODE
        
        print("Initializing Environment...")
        env = Grid3D(grid_size)
        rng = random.Random(seed)
        env.generate_random_obstacles(num_obstacles, start, goal, rand_instance=rng)
        
        llm_waypoints = None
        llm_info = None
        inference_time = 0.0

    print(f"Grid: {grid_size}, Start: {start}, Goal: {goal}")
    print(f"Generated/Loaded {len(env.obstacles)} obstacles.")
    
    experiment_record = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "is_replay": replay_data is not None,
        "seed": seed,
        "config": {
            "GRID_SIZE": grid_size,
            "START": start,
            "GOAL": goal,
            "NUM_OBSTACLES": num_obstacles,
            "PROMPT_MODE": prompt_mode,
            "LLM_TEMPERATURE": cfg.LLM_TEMPERATURE,
            "PRIORITY_VARIANT": cfg.PRIORITY_VARIANT,
            "CLOSED_NODE_VARIANT": cfg.CLOSED_NODE_VARIANT
        },
        "obstacles": list(env.obstacles)
    }
    
    # ---------------- STANDARD A* ----------------
    print("\nSTANDARD A*")
    t0_std = time.perf_counter()
    std_path, std_metrics = standard_astar(start, goal, env)
    t1_std = time.perf_counter()
    std_metrics["search_time"] = t1_std - t0_std
    
    if std_path:
        std_val_result, std_val_reason = validate_path(std_path, env, start, goal)
        print("Path found")
        print(f"Path length (nodes): {std_metrics.get('path_length', 0)}")
        print(f"Path cost: {std_metrics.get('path_cost', 0):.2f}")
    else:
        std_val_result, std_val_reason = False, "No path returned"
        print("No path found")
        
    print(f"Termination: {std_metrics.get('termination_reason')}")
    print(f"Nodes expanded: {std_metrics['expanded_nodes']}")
    print(f"Search time: {std_metrics['search_time']:.4f} s")
    print(f"Validation: {std_val_result} ({std_val_reason})")
    
    experiment_record["standard_astar"] = {
        "metrics": std_metrics,
        "validation_result": std_val_result,
        "validation_reason": std_val_reason,
        "path": std_path
    }
    
    # ---------------- LLM INFERENCE ----------------
    print("\nLLM")
    if not replay_data:
        llm = LLMPlanner()
        t0_llm = time.perf_counter()
        llm_info = llm.generate_targets(start, goal, env)
        t1_llm = time.perf_counter()
        llm_waypoints = llm_info.get("waypoints", [])
        inference_time = t1_llm - t0_llm
        llm_info["inference_time"] = inference_time
    
    print(f"Waypoints: {llm_waypoints}")
    print(f"LLM time: {inference_time:.4f} s")
    experiment_record["llm"] = llm_info
    
    # ---------------- LLM-A* ----------------
    print("\nLLM-A*")
    t0_llma = time.perf_counter()
    llm_path, llm_metrics = llm_astar(start, goal, env, llm_waypoints)
    t1_llma = time.perf_counter()
    
    llm_metrics["search_time"] = t1_llma - t0_llma
    llm_metrics["total_pipeline_time"] = llm_metrics["search_time"] + inference_time
    
    if llm_path:
        llm_val_result, llm_val_reason = validate_path(llm_path, env, start, goal)
        print("Path found")
        print(f"Path length (nodes): {llm_metrics.get('path_length', 0)}")
        print(f"Path cost: {llm_metrics.get('path_cost', 0):.2f}")
    else:
        llm_val_result, llm_val_reason = False, "No path returned"
        print("No path found")
        
    print(f"Termination: {llm_metrics.get('termination_reason')}")
    print(f"Nodes expanded: {llm_metrics['expanded_nodes']}")
    print(f"Waypoints reached: {llm_metrics.get('waypoints_reached', 0)}")
    print(f"Search time: {llm_metrics['search_time']:.4f} s")
    print(f"Total pipeline time: {llm_metrics['total_pipeline_time']:.4f} s")
    print(f"Validation: {llm_val_result} ({llm_val_reason})")
    
    experiment_record["llm_astar"] = {
        "metrics": llm_metrics,
        "validation_result": llm_val_result,
        "validation_reason": llm_val_reason,
        "path": llm_path
    }
    
    # ---------------- SAVE ----------------
    os.makedirs("results", exist_ok=True)
    result_file = f"results/experiment_{run_id}.json"
    with open(result_file, "w") as f:
        json.dump(experiment_record, f, indent=2)
    print(f"\nExperiment record saved to {result_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        replay_file = sys.argv[1]
        with open(replay_file, "r") as f:
            data = json.load(f)
        run_experiment(data)
    else:
        run_experiment()
