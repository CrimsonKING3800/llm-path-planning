import os
import json
import time
import sys
sys.path.append('experiments')
from utils import generate_env, generate_oracle_waypoints, generate_perturbed_waypoints, generate_random_waypoints, generate_adversarial_waypoints
import astar3d

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "experiments", "results")

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

def run_experiment_2_corrected():
    print("Running Corrected Experiment 2: Waypoint Quality vs Search Performance")
    results = []
    
    for trial in range(20):
        seed = 2000 + trial
        env, start, goal = generate_env((20, 20, 5), 0.15, seed)
        path_opt, metrics_opt = run_search_with_timing(astar3d.dijkstra_search, start, goal, env)
        
        if not path_opt:
            continue
            
        optimal_cost = metrics_opt['path_cost']
        oracle_wps = generate_oracle_waypoints(path_opt, 3)
        near_wps = generate_perturbed_waypoints(oracle_wps, env, max_perturb=1, seed=seed)
        random_wps = generate_random_waypoints(env, 3, start, goal, seed=seed)
        adv_wps = generate_adversarial_waypoints(env, 3, start, goal, seed=seed)
        
        conditions = {
            'oracle': oracle_wps,
            'near_optimal': near_wps,
            'random': random_wps,
            'adversarial': adv_wps,
            'none': []
        }
        
        trial_results = {'trial': trial, 'optimal_cost': optimal_cost, 'runs': {}}
        for cond_name, wps in conditions.items():
            if cond_name == 'none':
                path, metrics = run_search_with_timing(astar3d.standard_astar, start, goal, env)
            else:
                path, metrics = run_search_with_timing(astar3d.llm_astar, start, goal, env, wps)
                
            if path:
                cost = metrics['path_cost']
                opt_gap = (cost - optimal_cost) / optimal_cost * 100 if optimal_cost > 0 else 0
            else:
                cost = None
                opt_gap = None
                
            trial_results['runs'][cond_name] = {
                'path_found': path is not None,
                'path_cost': cost,
                'optimality_gap': opt_gap,
                'expanded': metrics['expanded_nodes'] if metrics else None,
                'generated': metrics['generated_nodes'] if metrics else None,
                'search_time': metrics.get('search_time') if metrics else None,
                'waypoints_generated': len(wps) if cond_name != 'none' else 0
            }
        print(f"Trial {trial} completed. Adv wps generated: {len(adv_wps)}")
        results.append(trial_results)
    save_result("experiment_2_corrected", results)
    print("Done. Saved to experiment_2_corrected.json")

if __name__ == '__main__':
    run_experiment_2_corrected()
