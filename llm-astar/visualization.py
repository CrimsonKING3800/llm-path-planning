import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def visualize_path(env, start, goal, waypoints, path):
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot obstacles
    obs_x = [o[0] for o in env.obstacles]
    obs_y = [o[1] for o in env.obstacles]
    obs_z = [o[2] for o in env.obstacles]
    ax.scatter(obs_x, obs_y, obs_z, c='gray', marker='s', alpha=0.1, label='Obstacles')
    
    # Plot path
    if path:
        path_x = [p[0] for p in path]
        path_y = [p[1] for p in path]
        path_z = [p[2] for p in path]
        ax.plot(path_x, path_y, path_z, c='blue', linewidth=2, label='A* Path')
    
    # Plot LLM Waypoints
    if waypoints:
        wp_x = [w[0] for w in waypoints]
        wp_y = [w[1] for w in waypoints]
        wp_z = [w[2] for w in waypoints]
        ax.scatter(wp_x, wp_y, wp_z, c='orange', marker='^', s=100, label='LLM Waypoints')
        
    # Plot Start and Goal
    ax.scatter(*start, c='green', marker='o', s=150, label='Start')
    ax.scatter(*goal, c='red', marker='*', s=200, label='Goal')
    
    ax.set_xlim(0, env.size[0])
    ax.set_ylim(0, env.size[1])
    ax.set_zlim(0, env.size[2])
    
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    
    plt.legend()
    plt.title("LLM-Guided 3D A* Path Planning")
    plt.show()
