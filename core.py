import json
import time
import os
import sys
from datetime import datetime
from enum import Enum
from typing import List, Dict, Union
import config
import ollama

# ==========================================
# 1. MOCK ENVIRONMENT & GLOBAL STATE
# ==========================================
WORLD_STATE = {
    "nodes": {
        
        "Node_Water_Pump_A": {"status": "Broken", "type": "Water", "population_affected": 5000, "criticality": "High"},
        "Node_Server_B": {"status": "Operational", "type": "Internet", "population_affected": 200, "criticality": "Low"},
        "Node_Power_Substation_C": {"status": "Broken", "type": "Power", "population_affected": 15000, "criticality": "Critical"},
        "Node_Relay_D": {"status": "Operational", "type": "Telecom", "population_affected": 1000, "criticality": "Medium"}
    },
    "crews": {
        "Crew_Alpha": {"status": "Available", "specialty": "General"},
        "Crew_Beta": {"status": "Busy", "specialty": "Electrical"},
        "Crew_Gamma": {"status": "Busy", "specialty": "Water"}
    }
}
#Above are the states that you are in, which crew are you going to assess, in order to fix the biggest problems

# ==========================================
# 2. TOOLS DEFINITION
# ==========================================
def detect_failure_nodes() -> List[str]:
    """Returns a list of IDs for nodes that are currently in 'Broken' status."""
    failures = []
    for node_id, data in WORLD_STATE["nodes"].items():
        if data["status"] == "Broken":
            failures.append(node_id)
    return failures

def estimate_impact(node_id: str) -> Dict[str, Union[str, int]]:
    """Returns impact metrics for a specific node."""
    node = WORLD_STATE["nodes"].get(node_id)
    if not node:
        return {"error": f"Node {node_id} not found."}
    return {
        "node_id": node_id,
        "type": node["type"],
        "population_affected": node["population_affected"],
        "criticality": node["criticality"]
    }

def assign_repair_crew(node_ids: List[str], crew_ids: List[str]) -> Dict[str, str]:
    """Assigns crews to nodes. Returns success/failure status."""
    results = {}
    if len(node_ids) != len(crew_ids):
        return {"error": "Mismatch between number of nodes and crews."}

    for i in range(len(node_ids)):
        n_id = node_ids[i]
        c_id = crew_ids[i]
        
        # Έλεγχος διαθεσιμότητας και ύπαρξης
        if n_id not in WORLD_STATE["nodes"] or c_id not in WORLD_STATE["crews"]:
             results[f"{n_id}-{c_id}"] = "Failed: Invalid ID"
             continue
             
        if WORLD_STATE["crews"][c_id]["status"] != "Available":
            results[f"{n_id}-{c_id}"] = f"Failed: {c_id} is Busy"
        else:
            WORLD_STATE["nodes"][n_id]["status"] = "Repairing"
            WORLD_STATE["crews"][c_id]["status"] = "Busy"
            results[f"{n_id}-{c_id}"] = "Success: Crew dispatched"

    return {"assignment_report": results}

# ==========================================
# 3. LLM INTERFACE
# ==========================================
def llm_call(system_prompt: str, user_context: str) -> str:
    """Calls the Ollama model with separate System and User messages."""
    try:
        response = ollama.chat(
            model='lfm2.5-thinking:1.2b',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_context}
            ],
            format='json',
            options={'temperature': 0.0} # 0.0 for maximum determinism
        )
        return response['message']['content']
    except Exception as e:
        print(f"LLM Error: {e}")
        return json.dumps({
            "thought": "LLM failed",
            "action": "finalize",
            "arguments": {}
        })

# ==========================================
# 4. AGENT FSM CLASS
# ==========================================
class AgentState(Enum):
    INIT = 0
    DETECT = 1
    ANALYZE = 2
    PLAN = 3
    ACT = 4 # Optional, included in PLAN for simplicity here
    FINAL = 5

class InfrastructureAgent:
    def __init__(self, max_steps=10):
        self.state = AgentState.INIT
        self.memory = {
            "context": {},      # Τρέχουσα γνώση (π.χ. λίστα βλαβών)
            "history": []       # Καταγραφή αποφάσεων
        }
        self.max_steps = max_steps
        self.step_count = 0

    def get_system_prompt(self):
        """Constructs the Static System Instruction."""
        # [cite_start]# [cite: 115-117] One-Shot Example & Protocol
        return """
You are an Infrastructure Failure Management Agent.
GOAL: Minimize social impact of network failures.

AVAILABLE TOOLS:
1. detect_failure_nodes() -> list: Returns broken node IDs.
2. estimate_impact(node_id: str) -> dict: Returns impact metrics.
3. assign_repair_crew(node_ids: list, crew_ids: list) -> dict: Assigns crews.
4. finalize() -> None: Ends the mission.

RESPONSE FORMAT:
You must respond with a JSON object containing:
- "thought": A brief reasoning for your action.
- "action": The name of the tool to call.
- "arguments": A dictionary of arguments for the tool.

ONE-SHOT EXAMPLE:
User Input: { "phase": "ANALYZE", "context": { "failures": ["Node_99"] } }
Model Response:
{
  "thought": "I found a failure at Node_99. I need to check its impact.",
  "action": "estimate_impact",
  "arguments": { "node_id": "Node_99" }
}
"""

    def step(self):
        self.step_count += 1
        print(f"\n=== STEP {self.step_count} | STATE: {self.state.name} ===")

        # --- 1. PREPARE INPUTS (Observe) ---
        # Κατασκευάζουμε το User Message με την τρέχουσα κατάσταση και μνήμη
        user_input = json.dumps({
            "phase": self.state.name,
            "context": self.memory["context"],
            "available_crews": [k for k,v in WORLD_STATE['crews'].items() if v['status'] == 'Available']
        })
        
        system_prompt = self.get_system_prompt()
        
        print(f"[PROMPT CONTEXT]: {user_input}") 

        # --- 2. THINK (LLM Call) ---
        raw_response = llm_call(system_prompt, user_input)
        
        try:
            decision = json.loads(raw_response)
            print(f"[RAW LLM]: {json.dumps(decision, indent=2)}")
        except json.JSONDecodeError:
            print("[ERROR] Invalid JSON from LLM")
            self.state = AgentState.FINAL
            return

        thought = decision.get("thought", "No thought provided")
        action_name = decision.get("action")
        args = decision.get("arguments", {})

        print(f"[THOUGHT]: {thought}")
        print(f"[ACTION]: Calling {action_name} with {args}")

        # --- 3. ACT (Tool Execution & Transitions) ---
        observation = None

        if action_name == "detect_failure_nodes":
            observation = detect_failure_nodes()
            # Update Memory
            self.memory['context']['failures'] = observation
            # Transition Logic
            if observation:
                self.state = AgentState.ANALYZE
            else:
                self.state = AgentState.FINAL

        elif action_name == "estimate_impact":
            observation = estimate_impact(**args)
            
            # Αποθήκευση στη μνήμη (λίστα impacts)
            if 'impact_reports' not in self.memory['context']:
                self.memory['context']['impact_reports'] = []
            self.memory['context']['impact_reports'].append(observation)
            
            # Transition: Αν έχουμε αναλύσει όλα τα known failures, πάμε στο PLAN
            # (Απλοϊκή λογική για το demo: πάμε κατευθείαν στο PLAN)
            self.state = AgentState.PLAN

        elif action_name == "assign_repair_crew":
            observation = assign_repair_crew(**args)
            self.memory['context']['repair_status'] = observation
            self.state = AgentState.FINAL

        elif action_name == "finalize":
            observation = "Mission Accomplished."
            self.state = AgentState.FINAL
            
        else:
            observation = "Error: Unknown tool."

        print(f"[OBSERVATION]: {observation}")
        
        # Save step to history
        self.memory['history'].append({
            "step": self.step_count,
            "state": self.state.name,
            "thought": thought,
            "action": action_name,
            "result": observation
        })

    def save_run_data(self):
        if config and hasattr(config, 'runs_path') and os.path.exists(config.runs_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"run_{timestamp}.json"
            filepath = os.path.join(config.runs_path, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=4, ensure_ascii=False)
            print(f"\n[SYSTEM] Run data saved to: {filepath}")

    def run(self):
        print("--- INFRASTRUCTURE AGENT STARTED ---")
        self.state = AgentState.DETECT # Force Start State
        
        while self.state != AgentState.FINAL and self.step_count < self.max_steps:
            self.step()
            time.sleep(1)

        print("\n--- AGENT FINISHED ---")
        # Validation Print
        print("Final World State (Check if nodes are Repairing):")
        print(json.dumps(WORLD_STATE["nodes"], indent=2))
        self.save_run_data()

if __name__ == "__main__":
    agent = InfrastructureAgent()
    agent.run()