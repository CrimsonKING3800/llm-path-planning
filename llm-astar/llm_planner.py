import json
import requests
from config import OLLAMA_URL, OLLAMA_MODEL

class LLMPlanner:
    def __init__(self, model_name=OLLAMA_MODEL):
        self.model_name = model_name

    def generate_targets(self, start, goal, env):
        # We sample a few obstacles to not overload the prompt
        obs_sample = list(env.obstacles)[:30] 
        
        prompt = f"""You are a 3D path planning assistant.

Environment:
Grid size: {env.size[0]} x {env.size[1]} x {env.size[2]}

Start:
{start}

Goal:
{goal}

Sample of Obstacles (x, y, z):
{obs_sample}

Suggest 3 to 5 intermediate waypoints that would help a path planner navigate around the obstacles from Start to Goal.
Return ONLY valid JSON in this exact format, with no markdown formatting or other text:
{{
    "waypoints": [
        [x1, y1, z1],
        [x2, y2, z2]
    ]
}}"""
        try:
            print(f"Connecting to Ollama at {OLLAMA_URL} with model {self.model_name}...")
            response = requests.post(OLLAMA_URL, json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            })
            
            if response.status_code == 200:
                result_text = response.json().get("response", "")
                return self.parse_and_validate_waypoints(result_text, env, start, goal)
            else:
                print(f"Error from Ollama API: {response.status_code}")
                return []
        except Exception as e:
            print(f"Failed to connect to Ollama or parse response: {e}")
            print("Make sure Ollama is running and the model is installed.")
            return []

    def parse_and_validate_waypoints(self, text, env, start, goal):
        try:
            data = json.loads(text)
            waypoints = data.get("waypoints", [])
            
            valid_waypoints = []
            for wp in waypoints:
                if len(wp) == 3:
                    wp_tuple = (int(wp[0]), int(wp[1]), int(wp[2]))
                    # Validate waypoint: inside grid and not an obstacle
                    if env.is_valid(wp_tuple) and not env.is_obstacle(wp_tuple):
                        if wp_tuple != start and wp_tuple != goal:
                            valid_waypoints.append(wp_tuple)
            
            print(f"LLM suggested {len(waypoints)} waypoints. {len(valid_waypoints)} are valid.")
            return valid_waypoints
        except json.JSONDecodeError:
            print("Failed to decode JSON from LLM response.")
            return []
        except Exception as e:
            print(f"Error validating waypoints: {e}")
            return []
