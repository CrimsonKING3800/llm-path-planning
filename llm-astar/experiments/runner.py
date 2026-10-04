import os
import json
import time
import copy
import random
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

def run_experiment_1():
    print("Running Experiment 1: Baseline Correctness Validation")
    results = []
    sizes = [(15,15,15), (20,20,20), (30,30,30)]
    densities = [0.05, 0.10, 0.20]
    
    for size in sizes:
        for density in densities:
            for trial in range(3): # 3 trials per size/density combination to get ~27 scenarios
                seed = hash((size, density, trial)) % 10000
                env, start, goal = generate_env(size, density, seed)
                
                path_dij, metrics_dij = run_search_with_timing(astar3d.dijkstra_search, start, goal, env)
                path_astar, metrics_astar = run_search_with_timing(astar3d.standard_astar, start, goal, env)
                
                if path_dij and path_astar:
                    cost_ratio = metrics_astar['path_cost'] / metrics_dij['path_cost'] if metrics_dij['path_cost'] > 0 else 1.0
                else:
                    cost_ratio = None
                    
                results.append({
                    'size': size,
                    'density': density,
                    'trial': trial,
                    'dijkstra_cost': metrics_dij['path_cost'] if metrics_dij else None,
                    'astar_cost': metrics_astar['path_cost'] if metrics_astar else None,
                    'cost_ratio': cost_ratio,
                    'dijkstra_expanded': metrics_dij['expanded_nodes'] if metrics_dij else None,
                    'astar_expanded': metrics_astar['expanded_nodes'] if metrics_astar else None
                })
    save_result("experiment_1", results)

def run_experiment_2():
    print("Running Experiment 2: Waypoint Quality vs Search Performance")
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
                'generated': metrics['generated_nodes'] if metrics else None
            }
        results.append(trial_results)
    save_result("experiment_2", results)

def run_experiment_3():
    print("Running Experiment 3: Sensitivity to Waypoint Count")
    results = []
    counts = [0, 1, 2, 3, 5, 8, 12, 20]
    
    for trial in range(10):
        seed = 3000 + trial
        env, start, goal = generate_env((25, 25, 5), 0.15, seed)
        path_opt, metrics_opt = run_search_with_timing(astar3d.dijkstra_search, start, goal, env)
        
        if not path_opt:
            continue
            
        optimal_cost = metrics_opt['path_cost']
        
        trial_results = {'trial': trial, 'optimal_cost': optimal_cost, 'runs': {}}
        for count in counts:
            if count == 0:
                path, metrics = run_search_with_timing(astar3d.standard_astar, start, goal, env)
            else:
                wps = generate_oracle_waypoints(path_opt, count)
                path, metrics = run_search_with_timing(astar3d.llm_astar, start, goal, env, wps)
                
            if path:
                cost = metrics['path_cost']
                opt_gap = (cost - optimal_cost) / optimal_cost * 100 if optimal_cost > 0 else 0
            else:
                cost = None
                opt_gap = None
                
            trial_results['runs'][str(count)] = {
                'path_found': path is not None,
                'path_cost': cost,
                'optimality_gap': opt_gap,
                'expanded': metrics['expanded_nodes'] if metrics else None,
                'search_time': metrics['search_time'] if metrics else None
            }
        results.append(trial_results)
    save_result("experiment_3", results)

def run_experiment_4():
    print("Running Experiment 4: Waypoint Ordering Sensitivity")
    results = []
    
    for trial in range(10):
        seed = 4000 + trial
        random.seed(seed)
        env, start, goal = generate_env((20, 20, 5), 0.15, seed)
        path_opt, metrics_opt = run_search_with_timing(astar3d.dijkstra_search, start, goal, env)
        
        if not path_opt:
            continue
            
        optimal_cost = metrics_opt['path_cost']
        oracle_wps = generate_oracle_waypoints(path_opt, 5)
        
        orderings = {
            'correct': oracle_wps,
            'reverse': list(reversed(oracle_wps)),
            'shuffle_1': random.sample(oracle_wps, len(oracle_wps)),
            'shuffle_2': random.sample(oracle_wps, len(oracle_wps)),
            'shuffle_3': random.sample(oracle_wps, len(oracle_wps))
        }
        
        trial_results = {'trial': trial, 'optimal_cost': optimal_cost, 'runs': {}}
        for name, wps in orderings.items():
            path, metrics = run_search_with_timing(astar3d.llm_astar, start, goal, env, wps)
            
            if path:
                cost = metrics['path_cost']
                opt_gap = (cost - optimal_cost) / optimal_cost * 100 if optimal_cost > 0 else 0
            else:
                cost = None
                opt_gap = None
                
            trial_results['runs'][name] = {
                'path_found': path is not None,
                'path_cost': cost,
                'optimality_gap': opt_gap,
                'expanded': metrics['expanded_nodes'] if metrics else None
            }
        results.append(trial_results)
    save_result("experiment_4", results)

def run_experiment_5():
    print("Running Experiment 5: Priority Variant Comparison")
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
                'expanded': metrics['expanded_nodes'] if metrics else None
            }
    
    # reset to default
    astar3d.PRIORITY_VARIANT = config.PRIORITY_VARIANT
    save_result("experiment_5", results)

def run_experiment_6():
    print("Running Experiment 6: Scalability Analysis")
    results = []
    sizes = [(10,10,10), (15,15,15), (20,20,20), (25,25,25), (30,30,30), (40,40,40)]
    
    for size in sizes:
        for trial in range(5):
            seed = 6000 + hash(size) % 1000 + trial
            env, start, goal = generate_env(size, 0.10, seed)
            
            # Since optimal path is needed for oracle waypoints, we run standard A* to get it quickly
            path_std, metrics_std = run_search_with_timing(astar3d.standard_astar, start, goal, env)
            
            if not path_std:
                continue
                
            oracle_wps = generate_oracle_waypoints(path_std, 3)
            path_llm, metrics_llm = run_search_with_timing(astar3d.llm_astar, start, goal, env, oracle_wps)
            
            results.append({
                'size': size[0], # Just store the dimension since they are cubes
                'trial': trial,
                'std_expanded': metrics_std['expanded_nodes'],
                'std_time': metrics_std['search_time'],
                'std_cost': metrics_std['path_cost'],
                'llm_expanded': metrics_llm['expanded_nodes'] if metrics_llm else None,
                'llm_time': metrics_llm['search_time'] if metrics_llm else None,
                'llm_cost': metrics_llm['path_cost'] if path_llm else None,
                'llm_reprio_time': metrics_llm.get('reprioritization_time', 0.0) if metrics_llm else None,
                'llm_peak_open': metrics_llm['peak_open_size'] if metrics_llm else None,
                'std_peak_open': metrics_std['peak_open_size']
            })
    save_result("experiment_6", results)

def run_experiment_7():
    print("Running Experiment 7: Obstacle Density Impact")
    results = []
    densities = [0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    
    for density in densities:
        for trial in range(5):
            seed = 7000 + int(density * 1000) + trial
            env, start, goal = generate_env((20, 20, 5), density, seed)
            
            path_opt, metrics_opt = run_search_with_timing(astar3d.standard_astar, start, goal, env)
            if not path_opt:
                continue # if no path exists, skip
                
            optimal_cost = metrics_opt['path_cost']
            oracle_wps = generate_oracle_waypoints(path_opt, 3)
            path_llm, metrics_llm = run_search_with_timing(astar3d.llm_astar, start, goal, env, oracle_wps)
            
            if path_llm:
                cost = metrics_llm['path_cost']
                opt_gap = (cost - optimal_cost) / optimal_cost * 100 if optimal_cost > 0 else 0
            else:
                cost = None
                opt_gap = None
                
            results.append({
                'density': density,
                'trial': trial,
                'path_found': path_llm is not None,
                'path_cost': cost,
                'optimality_gap': opt_gap,
                'std_expanded': metrics_opt['expanded_nodes'],
                'llm_expanded': metrics_llm['expanded_nodes'] if metrics_llm else None
            })
    save_result("experiment_7", results)

def run_experiment_8():
    print("Running Experiment 8: Reprioritization Overhead Measurement")
    results = []
    sizes = [(15,15,15), (20,20,20), (30,30,30), (40,40,40)]
    counts = [3, 10, 20]
    
    for size in sizes:
        for count in counts:
            for trial in range(3):
                seed = 8000 + size[0]*100 + count + trial
                env, start, goal = generate_env(size, 0.10, seed)
                
                path_std, metrics_std = run_search_with_timing(astar3d.standard_astar, start, goal, env)
                if not path_std:
                    continue
                    
                oracle_wps = generate_oracle_waypoints(path_std, count)
                path_llm, metrics_llm = run_search_with_timing(astar3d.llm_astar, start, goal, env, oracle_wps)
                
                if path_llm:
                    total_time = metrics_llm['search_time']
                    reprio_time = metrics_llm.get('reprioritization_time', 0.0)
                    reprio_frac = reprio_time / total_time if total_time > 0 else 0
                    
                    results.append({
                        'size': size[0],
                        'count': count,
                        'trial': trial,
                        'total_time': total_time,
                        'reprio_time': reprio_time,
                        'reprio_fraction': reprio_frac,
                        'peak_open': metrics_llm['peak_open_size'],
                        'open_at_switches': metrics_llm.get('open_size_at_switches', [])
                    })
    save_result("experiment_8", results)

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_experiment_1()
    run_experiment_2()
    run_experiment_3()
    run_experiment_4()
    run_experiment_5()
    run_experiment_6()
    run_experiment_7()
    run_experiment_8()
    print("All experiments completed!")

if __name__ == "__main__":
    main()
