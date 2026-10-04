import heapq
import itertools
import time

from config import PRIORITY_VARIANT, CLOSED_NODE_VARIANT

def heuristic(a, b):
    # Euclidean distance
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

def target_cost(state, target, goal):
    if target is None:
        return 0
    if PRIORITY_VARIANT == "standard_goal" and target == goal:
        return 0
    return heuristic(state, target)

def reconstruct_path(parent, current):
    path = [current]
    while current in parent:
        current = parent[current]
        path.append(current)
    path.reverse()
    return path

def calculate_path_cost(path):
    if not path or len(path) < 2:
        return 0.0
    cost = 0.0
    for i in range(len(path)-1):
        cost += heuristic(path[i], path[i+1])
    return cost

def validate_path(path, env, start, goal):
    if path is None:
        return False, "Path is None"
    if not path:
        return False, "Path is empty"
    if path[0] != start:
        return False, f"Path does not start at configured start. Expected {start}, got {path[0]}"
    if path[-1] != goal:
        return False, f"Path does not end at configured goal. Expected {goal}, got {path[-1]}"
    
    for i in range(len(path)):
        if not env.is_valid(path[i]):
            return False, f"State {path[i]} is out of grid bounds"
        if env.is_obstacle(path[i]):
            return False, f"State {path[i]} is an obstacle"
        
        if i > 0:
            if not env.are_neighbors(path[i-1], path[i]):
                return False, f"Consecutive states {path[i-1]} and {path[i]} are not valid neighbors (movement rule violation)"
                
    return True, "Path is valid"

def validate_endpoints(start, goal, env):
    if not env.is_valid(start):
        return False, f"Start {start} is out of bounds"
    if env.is_obstacle(start):
        return False, f"Start {start} is an obstacle"
    if not env.is_valid(goal):
        return False, f"Goal {goal} is out of bounds"
    if env.is_obstacle(goal):
        return False, f"Goal {goal} is an obstacle"
    return True, "Valid"

def dijkstra_search(start, goal, env):
    metrics = {
        'expanded_nodes': 0,
        'generated_nodes': 0,
        'peak_open_size': 0,
        'termination_reason': 'Unknown'
    }
    
    valid, reason = validate_endpoints(start, goal, env)
    if not valid:
        metrics['termination_reason'] = f"Endpoint validation failed: {reason}"
        return None, metrics
        
    if start == goal:
        metrics['termination_reason'] = "Start equals goal"
        metrics['path_length'] = 1
        metrics['path_cost'] = 0.0
        return [start], metrics

    counter = itertools.count()
    OPEN = []
    heapq.heappush(OPEN, (0, next(counter), start))
    metrics['generated_nodes'] += 1
    metrics['peak_open_size'] = 1
    
    CLOSED = set()
    g_score = {start: 0}
    parent = {}
    
    while OPEN:
        metrics['peak_open_size'] = max(metrics['peak_open_size'], len(OPEN))
        g, _, current = heapq.heappop(OPEN)
        
        if g > g_score.get(current, float('inf')):
            continue
            
        if current == goal:
            path = reconstruct_path(parent, current)
            metrics['path_length'] = len(path)
            metrics['path_cost'] = calculate_path_cost(path)
            metrics['termination_reason'] = 'Goal reached'
            return path, metrics
            
        if current in CLOSED:
            continue
            
        metrics['expanded_nodes'] += 1
        CLOSED.add(current)
        
        for neighbor in env.get_neighbors_3d(current):
            movement_cost = heuristic(current, neighbor)
            tentative_g = g_score[current] + movement_cost
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                parent[neighbor] = current
                g_score[neighbor] = tentative_g
                metrics['generated_nodes'] += 1
                heapq.heappush(OPEN, (tentative_g, next(counter), neighbor))
                
    metrics['termination_reason'] = 'OPEN set exhausted'
    return None, metrics

def llm_astar(start, goal, env, targets):
    metrics = {
        'expanded_nodes': 0,
        'generated_nodes': 0,
        'waypoints_reached': 0,
        'open_size_at_switches': [],
        'peak_open_size': 0,
        'reprioritization_time': 0.0,
        'termination_reason': 'Unknown'
    }
    
    valid, reason = validate_endpoints(start, goal, env)
    if not valid:
        metrics['termination_reason'] = f"Endpoint validation failed: {reason}"
        return None, metrics
        
    if start == goal:
        metrics['termination_reason'] = "Start equals goal"
        metrics['path_length'] = 1
        metrics['path_cost'] = 0.0
        return [start], metrics
    
    if not targets:
        # Fallback to standard A* if no waypoints
        path, std_metrics = standard_astar(start, goal, env)
        metrics.update(std_metrics)
        return path, metrics

    waypoint_targets = targets + [goal]
    current_target_idx = 0
    current_target = waypoint_targets[current_target_idx]
    
    counter = itertools.count()
    OPEN = []
    # Push tuple: (f_score, g_score, counter, state)
    heapq.heappush(OPEN, (heuristic(start, goal) + target_cost(start, current_target, goal), 0, next(counter), start))
    metrics['generated_nodes'] += 1
    
    CLOSED = set()
    g_score = {start: 0}
    parent = {}
    
    while OPEN:
        metrics['peak_open_size'] = max(metrics['peak_open_size'], len(OPEN))
        f, g, _, current = heapq.heappop(OPEN)
        
        # Stale entry check
        if g > g_score.get(current, float('inf')):
            continue
        
        if current == goal:
            path = reconstruct_path(parent, current)
            metrics['path_length'] = len(path)
            metrics['path_cost'] = calculate_path_cost(path)
            metrics['termination_reason'] = 'Goal reached'
            return path, metrics
            
        if current in CLOSED:
            continue
            
        metrics['expanded_nodes'] += 1
        CLOSED.add(current)
        
        # Check if we reached the current LLM target
        if current == current_target:
            metrics['waypoints_reached'] += 1
            metrics['open_size_at_switches'].append(len(OPEN))
            current_target_idx += 1
            if current_target_idx < len(waypoint_targets):
                current_target = waypoint_targets[current_target_idx]
                
                # Reprioritize OPEN set with the new target
                t0_reprio = time.time()
                new_OPEN = []
                for _, old_g, c, state in OPEN:
                    new_f = old_g + heuristic(state, goal) + target_cost(state, current_target, goal)
                    new_OPEN.append((new_f, old_g, c, state))
                heapq.heapify(new_OPEN)
                OPEN = new_OPEN
                metrics['reprioritization_time'] += (time.time() - t0_reprio)

                
        for neighbor in env.get_neighbors_3d(current):
            movement_cost = heuristic(current, neighbor)
            tentative_g = g_score[current] + movement_cost
            
            if neighbor in CLOSED:
                if CLOSED_NODE_VARIANT == "reopening" and tentative_g < g_score[neighbor]:
                    CLOSED.remove(neighbor)
                else:
                    continue
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                parent[neighbor] = current
                g_score[neighbor] = tentative_g
                metrics['generated_nodes'] += 1
                
                f_score = tentative_g + heuristic(neighbor, goal) + target_cost(neighbor, current_target, goal)
                heapq.heappush(OPEN, (f_score, tentative_g, next(counter), neighbor))
                
    metrics['termination_reason'] = 'OPEN set exhausted'
    return None, metrics

def standard_astar(start, goal, env):
    metrics = {
        'expanded_nodes': 0,
        'generated_nodes': 0,
        'peak_open_size': 0,
        'termination_reason': 'Unknown'
    }
    
    valid, reason = validate_endpoints(start, goal, env)
    if not valid:
        metrics['termination_reason'] = f"Endpoint validation failed: {reason}"
        return None, metrics
        
    if start == goal:
        metrics['termination_reason'] = "Start equals goal"
        metrics['path_length'] = 1
        metrics['path_cost'] = 0.0
        return [start], metrics

    counter = itertools.count()
    OPEN = []
    heapq.heappush(OPEN, (heuristic(start, goal), 0, next(counter), start))
    metrics['generated_nodes'] += 1
    
    CLOSED = set()
    g_score = {start: 0}
    parent = {}
    
    while OPEN:
        metrics['peak_open_size'] = max(metrics['peak_open_size'], len(OPEN))
        f, g, _, current = heapq.heappop(OPEN)
        
        # Stale entry check
        if g > g_score.get(current, float('inf')):
            continue
        
        if current == goal:
            path = reconstruct_path(parent, current)
            metrics['path_length'] = len(path)
            metrics['path_cost'] = calculate_path_cost(path)
            metrics['termination_reason'] = 'Goal reached'
            return path, metrics
            
        if current in CLOSED:
            continue
            
        metrics['expanded_nodes'] += 1
        CLOSED.add(current)
        
        for neighbor in env.get_neighbors_3d(current):
            movement_cost = heuristic(current, neighbor)
            tentative_g = g_score[current] + movement_cost
            
            if neighbor in CLOSED:
                if CLOSED_NODE_VARIANT == "reopening" and tentative_g < g_score[neighbor]:
                    CLOSED.remove(neighbor)
                else:
                    continue
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                parent[neighbor] = current
                g_score[neighbor] = tentative_g
                metrics['generated_nodes'] += 1
                
                f_score = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(OPEN, (f_score, tentative_g, next(counter), neighbor))
                
    metrics['termination_reason'] = 'OPEN set exhausted'
    return None, metrics
