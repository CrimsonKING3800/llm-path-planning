# Configuration for LLM-A* Path Planning

GRID_SIZE = (100, 100, 50)
START = (2, 3, 1)
GOAL = (95, 95, 45)
NUM_OBSTACLES = 25000

OLLAMA_URL = "http://localhost:11434/api/generate"
# You might need to change this model name to the one you have downloaded (e.g., 'llama3', 'mistral')
OLLAMA_MODEL = "qwen2.5:7b" 
LLM_TEMPERATURE = 0.0
LLM_TIMEOUT_SECONDS = 30.0

# Prompt modes: "arbitrary_subset", "seeded_random_sample", "compact_density", "exact"
PROMPT_MODE = "compact_density"
COMPACT_BLOCK_SIZE = 10
COMPACT_MAX_BLOCKS = 100

# Priority variants: "baseline" (double-counts goal heuristic), "standard_goal" (standard A* when targeting goal)
PRIORITY_VARIANT = "baseline"

# Algorithm variants: "baseline" (no reopening), "reopening" (allows CLOSED nodes to be reopened if a shorter path is found)
CLOSED_NODE_VARIANT = "baseline"
