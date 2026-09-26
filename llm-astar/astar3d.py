import heapq

def heuristic(a, b):
    # Euclidean distance
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5

def target_cost(state, target):
    return heuristic(state, target)

def reconstruct_path(parent, current):
    path = [current]
    while current in parent:
        current = parent[current]
        path.append(current)
    path.reverse()
    return path

def llm_astar(start, goal, env, targets):
    expanded_nodes = 0
    waypoint_targets = targets + [goal]
    
    current_target_idx = 0
    current_target = waypoint_targets[current_target_idx]
    
    OPEN = []
    # Push tuple: (f_score, g_score, item_id, state)
    heapq.heappush(OPEN, (heuristic(start, goal) + target_cost(start, current_target), 0, id(start), start))
    
    CLOSED = set()
    g_score = {start: 0}
    parent = {}
    
    while OPEN:
        f, g, _, current = heapq.heappop(OPEN)
        
        if current == goal:
            return reconstruct_path(parent, current), expanded_nodes
            
        if current in CLOSED:
            continue
            
        expanded_nodes += 1
        CLOSED.add(current)
        
        # Check if we reached the current LLM target
        if current == current_target:
            current_target_idx += 1
            if current_target_idx < len(waypoint_targets):
                current_target = waypoint_targets[current_target_idx]
                
                # Reprioritize OPEN set with the new target
                new_OPEN = []
                for _, old_g, item_id, state in OPEN:
                    new_f = old_g + heuristic(state, goal) + target_cost(state, current_target)
                    new_OPEN.append((new_f, old_g, item_id, state))
                heapq.heapify(new_OPEN)
                OPEN = new_OPEN
                
        for neighbor in env.get_neighbors_3d(current):
            if neighbor in CLOSED:
                continue
                
            movement_cost = heuristic(current, neighbor)
            tentative_g = g_score[current] + movement_cost
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                parent[neighbor] = current
                g_score[neighbor] = tentative_g
                
                f_score = tentative_g + heuristic(neighbor, goal) + target_cost(neighbor, current_target)
                heapq.heappush(OPEN, (f_score, tentative_g, id(neighbor), neighbor))
                
    return None, expanded_nodes

def standard_astar(start, goal, env):
    expanded_nodes = 0
    OPEN = []
    heapq.heappush(OPEN, (heuristic(start, goal), 0, id(start), start))
    
    CLOSED = set()
    g_score = {start: 0}
    parent = {}
    
    while OPEN:
        f, g, _, current = heapq.heappop(OPEN)
        
        if current == goal:
            return reconstruct_path(parent, current), expanded_nodes
            
        if current in CLOSED:
            continue
            
        expanded_nodes += 1
        CLOSED.add(current)
        
        for neighbor in env.get_neighbors_3d(current):
            if neighbor in CLOSED:
                continue
                
            movement_cost = heuristic(current, neighbor)
            tentative_g = g_score[current] + movement_cost
            
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                parent[neighbor] = current
                g_score[neighbor] = tentative_g
                
                f_score = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(OPEN, (f_score, tentative_g, id(neighbor), neighbor))
                
    return None, expanded_nodes
