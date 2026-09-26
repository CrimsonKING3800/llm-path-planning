import time
import random
from config import GRID_SIZE, START, GOAL, NUM_OBSTACLES
from environment import Grid3D
from llm_planner import LLMPlanner
from astar3d import llm_astar, standard_astar
from visualization import visualize_path

def main():
    print("Initializing Environment...")
    env = Grid3D(GRID_SIZE)
    random.seed(42)
    env.generate_random_obstacles(NUM_OBSTACLES, START, GOAL)
    
    print(f"Grid: {GRID_SIZE}, Start: {START}, Goal: {GOAL}")
    print(f"Generated {len(env.obstacles)} obstacles.")
    
    print("\nSTANDARD A*")
    t0_std = time.time()
    std_path, std_nodes = standard_astar(START, GOAL, env)
    t1_std = time.time()
    if std_path:
        print("Path found")
        print(f"Path length: {len(std_path)}")
    else:
        print("No path found")
    print(f"Nodes expanded: {std_nodes}")
    print(f"Search time: {t1_std - t0_std:.2f} s")
    
    print("\nLLM")
    llm = LLMPlanner()
    t0_llm = time.time()
    waypoints = llm.generate_targets(START, GOAL, env)
    t1_llm = time.time()
    print(f"Waypoints: {waypoints}")
    print(f"LLM time: {t1_llm - t0_llm:.2f} s")
    
    print("\nLLM-A*")
    t0_llma = time.time()
    llm_path, llm_nodes = llm_astar(START, GOAL, env, waypoints)
    t1_llma = time.time()
    
    if llm_path:
        print("Path found")
        print(f"Path length: {len(llm_path)}")
    else:
        print("No path found")
    print(f"Nodes expanded: {llm_nodes}")
    print(f"Search time: {t1_llma - t0_llma:.2f} s")

if __name__ == "__main__":
    main()
