import json
import time
import os
from datetime import datetime
from failure_cases import ALL_CASES
from environment import Grid3D
from astar3d import standard_astar, llm_astar, dijkstra_search, validate_path
from llm_planner import LLMPlanner
import config as cfg

def run_scenario(case):
    print(f"\n=======================================================")
    print(f"Running Case {case.case_id}: {case.name}")
    print(f"Hypothesis: {case.hypothesis}")
    print(f"=======================================================")
    
    env = case.get_env()
    
    results = {
        "case_id": case.case_id,
        "name": case.name,
        "hypothesis": case.hypothesis,
        "challenge": case.challenge,
        "timestamp": datetime.now().isoformat(),
        "config": {
            "grid_size": case.grid_size,
            "start": case.start,
            "goal": case.goal,
            "PRIORITY_VARIANT": cfg.PRIORITY_VARIANT,
            "CLOSED_NODE_VARIANT": cfg.CLOSED_NODE_VARIANT
        },
        "obstacles": list(env.obstacles),
        "manual_waypoints": case.manual_waypoints,
        "runs": {}
    }
    
    print("\n--- Dijkstra Optimal Reference ---")
    opt_path, opt_metrics = dijkstra_search(case.start, case.goal, env)
    optimal_cost = opt_metrics.get('path_cost', 0)
    print(f"Optimal Cost: {optimal_cost:.2f}")
    
    # 1. Standard A*
    print("\n--- Standard A* ---")
    t0 = time.perf_counter()
    std_path, std_metrics = standard_astar(case.start, case.goal, env)
    t1 = time.perf_counter()
    std_metrics["search_time"] = t1 - t0
    
    std_valid, std_reason = validate_path(std_path, env, case.start, case.goal) if std_path else (False, "No path")
    
    print(f"Termination: {std_metrics.get('termination_reason')}")
    print(f"Path Found: {std_path is not None}")
    print(f"Nodes Expanded: {std_metrics.get('expanded_nodes', 0)}")
    print(f"Path Cost: {std_metrics.get('path_cost', 0):.2f}")
    
    results["runs"]["Standard A*"] = {
        "metrics": std_metrics,
        "validation_result": std_valid,
        "validation_reason": std_reason,
        "path": std_path
    }
    
    # 2. LLM-A* (Injected)
    if case.manual_waypoints or case.case_id == "J": # run it even if empty, to prove termination
        print("\n--- LLM-A* (Injected Waypoints) ---")
        t0 = time.perf_counter()
        llm_path, llm_metrics = llm_astar(case.start, case.goal, env, case.manual_waypoints)
        t1 = time.perf_counter()
        llm_metrics["search_time"] = t1 - t0
        
        llm_valid, llm_reason = validate_path(llm_path, env, case.start, case.goal) if llm_path else (False, "No path")
        
        print(f"Termination: {llm_metrics.get('termination_reason')}")
        print(f"Path Found: {llm_path is not None}")
        print(f"Nodes Expanded: {llm_metrics.get('expanded_nodes', 0)}")
        print(f"Path Cost: {llm_metrics.get('path_cost', 0):.2f}")
        print(f"Waypoints Reached: {llm_metrics.get('waypoints_reached', 0)} / {len(case.manual_waypoints)}")
        
        results["runs"]["LLM-A* (Injected)"] = {
            "metrics": llm_metrics,
            "validation_result": llm_valid,
            "validation_reason": llm_reason,
            "path": llm_path
        }
        
    for var_name, var_waypoints in case.waypoint_variants.items():
        run_name = f"LLM-A* (Variant: {var_name})"
        print(f"\n--- {run_name} ---")
        t0 = time.perf_counter()
        llm_path, llm_metrics = llm_astar(case.start, case.goal, env, var_waypoints)
        t1 = time.perf_counter()
        llm_metrics["search_time"] = t1 - t0
        
        llm_valid, llm_reason = validate_path(llm_path, env, case.start, case.goal) if llm_path else (False, "No path")
        
        results["runs"][run_name] = {
            "metrics": llm_metrics,
            "validation_result": llm_valid,
            "validation_reason": llm_reason,
            "path": llm_path
        }

    # 3. LLM-A* (Generated) - Specifically for Case E to test representation
    if case.case_id == "E":
        for mode in ["exact", "compact_density"]:
            print(f"\n--- LLM-A* (Generated - {mode}) ---")
            planner = LLMPlanner(prompt_mode=mode)
            
            t0_inf = time.perf_counter()
            llm_info = planner.generate_targets(case.start, case.goal, env)
            t1_inf = time.perf_counter()
            inference_time = t1_inf - t0_inf
            llm_info["inference_time"] = inference_time
            
            waypoints = llm_info.get("waypoints", [])
            print(f"LLM generated {len(waypoints)} valid waypoints in {inference_time:.2f}s.")
            
            t0 = time.perf_counter()
            gen_path, gen_metrics = llm_astar(case.start, case.goal, env, waypoints)
            t1 = time.perf_counter()
            
            gen_metrics["search_time"] = t1 - t0
            gen_metrics["total_pipeline_time"] = gen_metrics["search_time"] + inference_time
            gen_valid, gen_reason = validate_path(gen_path, env, case.start, case.goal) if gen_path else (False, "No path")
            
            results["runs"][f"LLM-A* ({mode})"] = {
                "llm_info": llm_info,
                "metrics": gen_metrics,
                "validation_result": gen_valid,
                "validation_reason": gen_reason,
                "path": gen_path
            }
            
    # For Case I, do repetitions to smooth out timings
    if case.case_id == "I":
        for i in range(4): # 4 more runs (1 original + 4 = 5 total)
            standard_astar(case.start, case.goal, env)
            llm_astar(case.start, case.goal, env, case.manual_waypoints)

    results["optimal_cost"] = optimal_cost
    # Save case JSON
    os.makedirs("failure_results", exist_ok=True)
    with open(f"failure_results/case_{case.case_id}.json", "w") as f:
        json.dump(results, f, indent=2)
        
    return results

def generate_markdown_report(all_results):
    report = "# LLM-A* Failure Case Experiments\n\n"
    report += "This report documents deliberate, reproducible failure cases for the LLM-A* path-planning algorithm.\n\n"
    
    for res in all_results:
        report += f"## Case {res['case_id']}: {res['name']}\n"
        report += f"**Hypothesis:** {res['hypothesis']}\n\n"
        report += f"**Challenge:** {res['challenge']}\n\n"
        
        # Summary Table
        report += "| Algorithm | Path Found | Path Cost | Ratio | Nodes Gen | Nodes Exp | Peak OPEN | WPs Reached | Time (s) | Termination |\n"
        report += "|---|---|---|---|---|---|---|---|---|---|\n"
        
        opt_cost = res.get("optimal_cost", 0)
        
        for run_name, run_data in res['runs'].items():
            metrics = run_data['metrics']
            path_found = run_data['path'] is not None
            cost = metrics.get('path_cost', 0)
            cost_str = f"{cost:.2f}" if path_found else "N/A"
            ratio_str = f"{(cost/opt_cost):.2f}" if path_found and opt_cost > 0 else "N/A"
            nodes_exp = metrics.get('expanded_nodes', 0)
            nodes_gen = metrics.get('generated_nodes', 0)
            peak_open = metrics.get('peak_open_size', 0)
            wp_reached = metrics.get('waypoints_reached', 0)
            t = f"{metrics.get('search_time', 0):.4f}"
            term = metrics.get('termination_reason', 'Unknown')
            report += f"| {run_name} | {path_found} | {cost_str} | {ratio_str} | {nodes_gen} | {nodes_exp} | {peak_open} | {wp_reached} | {t} | {term} |\n"
        
        report += "\n**Analysis & Classification:**\n"
        
        # Add automatic brief analysis
        std_run = res['runs'].get('Standard A*')
        inj_run = res['runs'].get('LLM-A* (Injected)')
        
        if std_run and inj_run:
            std_nodes = std_run['metrics'].get('expanded_nodes', 0)
            inj_nodes = inj_run['metrics'].get('expanded_nodes', 0)
            std_cost = std_run['metrics'].get('path_cost', 0)
            inj_cost = inj_run['metrics'].get('path_cost', 0)
            
            if not std_run['path'] and not inj_run['path']:
                report += "- Classification: Correctness Check\n"
                report += "- Both algorithms correctly identified no path exists.\n"
            elif inj_nodes > std_nodes:
                report += f"- Classification: Confirmed Search Inefficiency\n"
                report += f"- LLM-A* expanded {inj_nodes} nodes vs Standard A*'s {std_nodes} nodes, a {(inj_nodes/max(1,std_nodes)):.2f}x increase.\n"
            elif inj_run['path'] and std_run['path']:
                if inj_cost > opt_cost + 0.01:
                    report += f"- Classification: Confirmed Suboptimality\n"
                    report += f"- LLM-A* found a path with cost {inj_cost:.2f}, optimal is {opt_cost:.2f}.\n"
                else:
                    report += "- Classification: Stress case / Hypothesis not strongly reproduced\n"
                    
        report += "\n---\n"
        
    with open("failure_results/FAILURE_REPORT.md", "w") as f:
        f.write(report)
    print("\nGenerated failure_results/FAILURE_REPORT.md")

if __name__ == "__main__":
    results = []
    for case in ALL_CASES:
        res = run_scenario(case)
        results.append(res)
    
    generate_markdown_report(results)
