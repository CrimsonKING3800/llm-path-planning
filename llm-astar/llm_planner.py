import json
import requests
import random
from config import OLLAMA_URL, OLLAMA_MODEL, LLM_TEMPERATURE, PROMPT_MODE, COMPACT_BLOCK_SIZE, COMPACT_MAX_BLOCKS, LLM_TIMEOUT_SECONDS

class LLMPlanner:
    def __init__(self, model_name=OLLAMA_MODEL, temperature=LLM_TEMPERATURE, prompt_mode=PROMPT_MODE):
        self.model_name = model_name
        self.temperature = temperature
        self.prompt_mode = prompt_mode

    def get_env_representation(self, env):
        omitted = 0
        if self.prompt_mode == "compact_density":
            # Divide grid into blocks and count obstacles
            blocks = {}
            for obs in env.obstacles:
                bx = obs[0] // COMPACT_BLOCK_SIZE
                by = obs[1] // COMPACT_BLOCK_SIZE
                bz = obs[2] // COMPACT_BLOCK_SIZE
                blocks[(bx, by, bz)] = blocks.get((bx, by, bz), 0) + 1
            
            rep = f"Mode: {self.prompt_mode} (Block Density)\n"
            rep += f"Grid is divided into {COMPACT_BLOCK_SIZE}x{COMPACT_BLOCK_SIZE}x{COMPACT_BLOCK_SIZE} blocks. The following blocks contain obstacles (x, y, z blocks):\n"
            sorted_blocks = sorted(blocks.items(), key=lambda item: item[1], reverse=True)[:COMPACT_MAX_BLOCKS]
            for block, count in sorted_blocks:
                rep += f"Block {block} (spans {block[0]*COMPACT_BLOCK_SIZE}-{block[0]*COMPACT_BLOCK_SIZE+(COMPACT_BLOCK_SIZE-1)}, {block[1]*COMPACT_BLOCK_SIZE}-{block[1]*COMPACT_BLOCK_SIZE+(COMPACT_BLOCK_SIZE-1)}, {block[2]*COMPACT_BLOCK_SIZE}-{block[2]*COMPACT_BLOCK_SIZE+(COMPACT_BLOCK_SIZE-1)}): {count} obstacles\n"
            if len(blocks) > COMPACT_MAX_BLOCKS:
                omitted = sum(count for b, count in sorted(blocks.items(), key=lambda item: item[1], reverse=True)[COMPACT_MAX_BLOCKS:])
                rep += f"... and {len(blocks) - COMPACT_MAX_BLOCKS} other blocks with obstacles ({omitted} obstacles omitted).\n"
            rep += f"\nLimitations: This representation shows obstacle density per {COMPACT_BLOCK_SIZE}^3 block, not exact positions. It does not provide full visibility of all fine-grained obstacle coordinates.\n"
        
        elif self.prompt_mode == "arbitrary_subset":
            obs_sample = list(env.obstacles)[:30]
            omitted = max(0, len(env.obstacles) - 30)
            rep = f"Mode: {self.prompt_mode}\nSample of Obstacles (x, y, z):\n{obs_sample}\n"
            rep += f"\nLimitations: This is an arbitrary deterministic subset. {omitted} obstacles are omitted.\n"
            
        elif self.prompt_mode == "seeded_random_sample":
            rng = random.Random(42)
            obs_sample = rng.sample(list(env.obstacles), min(30, len(env.obstacles)))
            omitted = max(0, len(env.obstacles) - len(obs_sample))
            rep = f"Mode: {self.prompt_mode}\nSample of Obstacles (x, y, z):\n{obs_sample}\n"
            rep += f"\nLimitations: This is a random sample of obstacles. {omitted} obstacles are omitted.\n"
            
        elif self.prompt_mode == "exact":
            rep = f"Mode: {self.prompt_mode}\nAll Obstacles (x, y, z):\n{list(env.obstacles)}\n"
            rep += "\nLimitations: None. Exact representation.\n"
        
        else:
            rep = f"Mode: {self.prompt_mode}\nUnknown mode.\n"
            
        return rep, omitted

    def generate_targets(self, start, goal, env):
        env_info, omitted_count = self.get_env_representation(env)

        prompt = f"""You are a 3D path planning assistant.

Environment:
Grid size: {env.size[0]} x {env.size[1]} x {env.size[2]}
Movement connectivity: 26-connected (all adjacent cells in 3D). Diagonal movement is permitted as long as the destination cell is free.
Movement cost: Euclidean distance.

Start:
{start}

Goal:
{goal}

{env_info}
Suggest 3 to 5 intermediate waypoints that would help a path planner navigate around the obstacles from Start to Goal.
Return ONLY valid JSON in this exact format, with no markdown formatting or other text:
{{
    "waypoints": [
        [x1, y1, z1],
        [x2, y2, z2]
    ]
}}"""
        
        result_info = {
            "model": self.model_name,
            "settings": {"temperature": self.temperature, "format": "json"},
            "prompt_mode": self.prompt_mode,
            "omitted_obstacles": omitted_count,
            "prompt": prompt,
            "raw_response": "",
            "waypoints": [],
            "rejected_waypoints": [],
            "status": "pending",
            "error": None
        }
        
        try:
            print(f"Connecting to Ollama at {OLLAMA_URL} with model {self.model_name}...")
            response = requests.post(OLLAMA_URL, json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": self.temperature
                }
            }, timeout=LLM_TIMEOUT_SECONDS)
            
            if response.status_code == 200:
                result_text = response.json().get("response", "")
                result_info["raw_response"] = result_text
                parsed, rejected, parsing_error = self.parse_and_validate_waypoints(result_text, env, start, goal)
                result_info["waypoints"] = parsed
                result_info["rejected_waypoints"] = rejected
                if parsing_error:
                    result_info["status"] = "parsing_error"
                    result_info["error"] = parsing_error
                else:
                    result_info["status"] = "success"
            else:
                result_info["status"] = "http_error"
                result_info["error"] = f"HTTP {response.status_code}: {response.text}"
                print(f"Error from Ollama API: {response.status_code}")
        except requests.exceptions.Timeout:
            result_info["status"] = "timeout"
            result_info["error"] = f"Request timed out after {LLM_TIMEOUT_SECONDS}s"
            print(result_info["error"])
        except Exception as e:
            result_info["status"] = "connection_error"
            result_info["error"] = str(e)
            print(f"Failed to connect to Ollama or parse response: {e}")
            
        return result_info

    def parse_and_validate_waypoints(self, text, env, start, goal):
        valid_waypoints = []
        rejected_waypoints = []
        seen = set()
        parsing_error = None
        
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("JSON root is not an object")
                
            waypoints = data.get("waypoints")
            if waypoints is None:
                raise ValueError("Missing 'waypoints' field in JSON")
            if not isinstance(waypoints, list):
                raise ValueError("'waypoints' field is not a list")
            
            for wp in waypoints:
                if not isinstance(wp, list) or len(wp) != 3:
                    rejected_waypoints.append({"waypoint": wp, "reason": "Not a list of 3 coordinates"})
                    continue
                
                # Check for integral coordinates
                is_integral = True
                for coord in wp:
                    if isinstance(coord, int):
                        continue
                    if isinstance(coord, float) and coord.is_integer():
                        continue
                    is_integral = False
                    break
                    
                if not is_integral:
                    rejected_waypoints.append({"waypoint": wp, "reason": "Non-integral coordinates"})
                    continue
                
                wp_tuple = (int(wp[0]), int(wp[1]), int(wp[2]))
                
                # Check duplicates (preserve order)
                if wp_tuple in seen:
                    rejected_waypoints.append({"waypoint": wp_tuple, "reason": "Duplicate waypoint"})
                    continue
                
                seen.add(wp_tuple)
                
                # Validate waypoint: inside grid and not an obstacle
                if not env.is_valid(wp_tuple):
                    rejected_waypoints.append({"waypoint": wp_tuple, "reason": "Out of grid bounds"})
                elif env.is_obstacle(wp_tuple):
                    rejected_waypoints.append({"waypoint": wp_tuple, "reason": "On an obstacle"})
                elif wp_tuple == start or wp_tuple == goal:
                    rejected_waypoints.append({"waypoint": wp_tuple, "reason": "Same as start or goal"})
                else:
                    valid_waypoints.append(wp_tuple)
            
            print(f"LLM suggested {len(waypoints)} waypoints. {len(valid_waypoints)} are valid, {len(rejected_waypoints)} rejected.")
            for r in rejected_waypoints:
                print(f"Rejected {r['waypoint']}: {r['reason']}")
                
        except json.JSONDecodeError as e:
            parsing_error = f"JSON Decode Error: {str(e)}"
            print(parsing_error)
        except ValueError as e:
            parsing_error = f"Validation Error: {str(e)}"
            print(parsing_error)
        except Exception as e:
            parsing_error = f"Unexpected Error: {str(e)}"
            print(parsing_error)
            
        return valid_waypoints, rejected_waypoints, parsing_error
