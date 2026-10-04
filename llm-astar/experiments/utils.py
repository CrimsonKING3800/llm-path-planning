import random
import math
from environment import Grid3D
from astar3d import dijkstra_search

def generate_env(size, density, seed=None):
    if seed is not None:
        random.seed(seed)
    
    env = Grid3D(size)
    total_cells = size[0] * size[1] * size[2]
    num_obstacles = int(total_cells * density)
    
    # We choose start and goal before generating obstacles
    start = (0, 0, 0)
    goal = (size[0]-1, size[1]-1, size[2]-1)
    
    # generate_random_obstacles signature: num_obstacles, start, goal, rand_instance=None
    env.generate_random_obstacles(num_obstacles, start, goal, random)
    return env, start, goal

def get_optimal_path(env, start, goal):
    path, metrics = dijkstra_search(start, goal, env)
    return path, metrics

def generate_oracle_waypoints(path, num_waypoints):
    if not path or len(path) <= 2 or num_waypoints <= 0:
        return []
    
    # We exclude start and goal from the candidate path points
    candidates = path[1:-1]
    if not candidates:
        return []
        
    if num_waypoints >= len(candidates):
        return candidates
        
    # Sample evenly spaced points
    indices = [int(i * (len(candidates) - 1) / (num_waypoints - 1)) for i in range(num_waypoints)] if num_waypoints > 1 else [len(candidates) // 2]
    return [candidates[i] for i in indices]

def generate_perturbed_waypoints(oracle_waypoints, env, max_perturb=2, seed=None):
    rng = random.Random(seed) if seed is not None else random.Random()
        
    perturbed = []
    for wp in oracle_waypoints:
        valid_neighbors = []
        for dx in range(-max_perturb, max_perturb + 1):
            for dy in range(-max_perturb, max_perturb + 1):
                for dz in range(-max_perturb, max_perturb + 1):
                    nx, ny, nz = wp[0] + dx, wp[1] + dy, wp[2] + dz
                    p = (nx, ny, nz)
                    if env.is_valid(p) and not env.is_obstacle(p):
                        valid_neighbors.append(p)
        if valid_neighbors:
            perturbed.append(rng.choice(valid_neighbors))
        else:
            perturbed.append(wp)
    return perturbed

def generate_random_waypoints(env, num_waypoints, start, goal, seed=None):
    rng = random.Random(seed) if seed is not None else random.Random()
        
    waypoints = set()
    attempts = 0
    while len(waypoints) < num_waypoints and attempts < 1000:
        x = rng.randint(0, env.size[0] - 1)
        y = rng.randint(0, env.size[1] - 1)
        z = rng.randint(0, env.size[2] - 1)
        p = (x, y, z)
        if not env.is_obstacle(p) and p != start and p != goal:
            waypoints.add(p)
        attempts += 1
    return list(waypoints)

def generate_adversarial_waypoints(env, num_waypoints, start, goal, seed=None):
    """Generate waypoints that are 'away' from the goal (adversarial)."""
    rng = random.Random(seed) if seed is not None else random.Random()
        
    waypoints = []
    
    # Goal is at (size[0]-1, ...,) and start is at (0, 0, 0)
    # Adversarial waypoints: high distance to goal
    candidates = []
    attempts = 0
    # Try to find enough candidate points to choose from
    while len(candidates) < 200 and attempts < 2000:
        x = rng.randint(0, env.size[0] - 1)
        y = rng.randint(0, env.size[1] - 1)
        z = rng.randint(0, env.size[2] - 1)
        p = (x, y, z)
        attempts += 1
        if not env.is_obstacle(p) and p != start and p != goal:
            if not any(c[1] == p for c in candidates):
                dist_to_goal = ((p[0]-goal[0])**2 + (p[1]-goal[1])**2 + (p[2]-goal[2])**2) ** 0.5
                candidates.append((dist_to_goal, p))
            
    # Sort descending by distance to goal
    candidates.sort(reverse=True, key=lambda x: x[0])
    
    for i in range(min(num_waypoints, len(candidates))):
        waypoints.append(candidates[i][1])
        
    if len(waypoints) < num_waypoints:
        print(f"WARNING: Requested {num_waypoints} adversarial waypoints but only found {len(waypoints)}")
        
    return waypoints
