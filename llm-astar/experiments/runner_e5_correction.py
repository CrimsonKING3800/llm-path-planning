import os
import json
import time
import copy
from utils import *
import astar3d
import config

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

def save_result(name, data):
    with open(os.path.join(RESULTS_DIR, f"{name}.json"), "w") as f:
        json.dump(data, f, indent=2)

def run_search_with_timing(search_fn, *args):
    t0 = time.time()
    path, metrics = search_fn(*args)
    t1 = time.time()
    if metrics:
        metrics['search_time'] = t1 - t0
    return path, metrics

def run_experiment_5_correction():
    print("Running Experiment 5 Correction: Priority Variant Comparison")
    results = []
    
    for trial in range(20):
        seed = 5000 + trial
        env, start, goal = generate_env((20, 20, 5), 0.15, seed)
        path_opt, metrics_opt = run_search_with_timing(astar3d.dijkstra_search, start, goal, env)
        
        if not path_opt:
            continue
            
        optimal_cost = metrics_opt['path_cost']
        oracle_wps = generate_oracle_waypoints(path_opt, 3)
        
        trial_results = {'trial': trial, 'optimal_cost': optimal_cost, 'runs': {}}
        
        for variant in ["baseline", "standard_goal"]:
            astar3d.PRIORITY_VARIANT = variant
            path, metrics = run_search_with_timing(astar3d.llm_astar, start, goal, env, oracle_wps)
            
            if path:
                cost = metrics['path_cost']
                opt_gap = (cost - optimal_cost) / optimal_cost * 100 if optimal_cost > 0 else 0
            else:
                cost = None
                opt_gap = None
                
            trial_results['runs'][variant] = {
                'path_found': path is not None,
                'path_cost': cost,
                'optimality_gap': opt_gap,
                'expanded': metrics['expanded_nodes'] if metrics else None,
                'search_time': metrics['search_time'] if metrics else None
            }
        # BUG FIX: appended trial_results to results, which was omitted in the original runner.py
        results.append(trial_results)
    
    # reset to default
    astar3d.PRIORITY_VARIANT = config.PRIORITY_VARIANT
    save_result("experiment_5_rerun", results)
    print("Experiment 5 rerun complete.")

if __name__ == "__main__":
    run_experiment_5_correction()
