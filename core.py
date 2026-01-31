import json, time, os, sys
from enum import Enum
from typing import Dict
from datetime import datetime

import config
from scenarios import jsonPicker 
from tools import toolList

# ==========================================
# 3. LLM INTERFACE
# ==========================================
def llm_call(system_prompt: str, user_context: str) -> Dict:
    try:
        if config.USE_CLOUD:
            import openai
            #κάνουμε import openai όχι γιατί χρησιμοποιούμε τα μοντέλα τους αλλά χρησιμοποιούμε το python client τους, για να εισάγουμε api key απο το groq
            #overiding base url
            base_url = "https://api.groq.com/openai/v1" if config.CLOUD_PROVIDER == "groq" else None #σύμφωνα με τα groq docs, για να κάνεις create chat completion χρησιμοποιείς το link
            client = openai.OpenAI(api_key=config.CLOUD_API_KEY, base_url=base_url)
            
            response = client.chat.completions.create(
                model=config.CLOUD_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_context}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            content = response.choices[0].message.content
            # Καθαρισμός αν το μοντέλο επιστρέψει markdown code block
            if content.strip().startswith("```json"):
                content = content.strip()[7:-3]
            elif content.strip().startswith("```"):
                content = content.strip()[3:-3]
            return json.loads(content)
        else:
            # Local Ollama fallback
            import ollama
            response = ollama.chat(model="qwen3:4b", messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context}
            ], format="json", options={"temperature": 0.1})
            return json.loads(response["message"]["content"])
    except Exception as e:
        return {"thought": f"LLM error: {str(e)}", "action": "none", "arguments": {}, "next_state": "FINAL"}

# ==========================================
# 4. FSM & AGENT
# ==========================================
class AgentState(Enum):
    DETECT, ANALYZE, PLAN, ACT, WAIT, FINAL = "DETECT", "ANALYZE", "PLAN", "ACT", "WAIT", "FINAL"

class InfrastructureAgent:
    def __init__(self, max_steps=20):
        self.state = AgentState.DETECT
        self.step_count = 0
        self.max_steps = max_steps
        self.memory = {"context": {}, "history": []}

    def get_system_prompt(self):
        base = """
            You are an Autonomous Infrastructure Failure Management Agent.
            GOAL: Analyze infrastructure failures and assign the best available repair crews based on criticality.
            
            AVAILABLE TOOLS:
            1. detect_failure_nodes() -> list: Returns broken node IDs.
            2. estimate_impact(node_id: str) -> dict: Returns impact metrics (population, criticality).
            3. assign_repair_crew(node_ids: list, crew_ids: list) -> dict: Assigns crews to nodes.
            4. check_crew_availability() -> Dict: Crew IDs mapped to their current status ('Available' or 'Busy').
            5. none: Use this if you just want to change state without calling a tool.

            RULES FOR PLANNING:
            - You must match available crews to nodes. 
            - 'General' crews can fix anything. Specialized crews only fix their type.
            - Prioritize 'Critical' nodes over 'High/Medium/Low'.
            - CRITICAL PRIORITY: If multiple nodes are broken, you MUST compare their population. ALWAYS prioritize fixing the node with the HIGHEST population first.

            RESPONSE FORMAT:
            You must respond ONLY with a valid JSON object containing:
            - "thought": Explain your reasoning (Chain-of-Thought).
            - "action": The name of the tool to call.
            - "arguments": A dictionary of arguments for the tool.
            - "next_state": The next state to transition to (DETECT, ANALYZE, PLAN, ACT, WAIT, FINAL).
            """
        
        # State-specific dynamic instructions to help the small model
        state_guidance = {
            AgentState.DETECT: "CURRENT STATE: DETECT. You MUST call 'detect_failure_nodes' to identify issues. Do NOT transition to FINAL yet.",
            AgentState.ANALYZE: "CURRENT STATE: ANALYZE. You MUST call 'estimate_impact' for one node from 'remaining_to_analyze'. If 'remaining_to_analyze' is empty, transition to PLAN.",
            AgentState.PLAN: "CURRENT STATE: PLAN. You MUST call 'assign_repair_crew' to fix 'failed_nodes'. If all nodes are assigned or no crews are available, transition to FINAL.",
            AgentState.WAIT: "CURRENT STATE: WAIT. No action needed. If no actions are available, Trasnition to FINAL."
        }
        
        return base + "\n" + state_guidance.get(self.state, "")

    def step(self):
        self.step_count += 1
        print(f"\n{'='*50}\nSTEP {self.step_count} | CURRENT STATE: {self.state.value}\n{'='*50}")

        # 1. OBSERVE: Gather context for the LLM
        available_crews = [c for c, d in config.WORLD_STATE["crews"].items() if d["status"] == "Available"]
        failures = self.memory["context"].get("failures", [])
        analyzed_reports = self.memory["context"].get("impact_reports", [])
        analyzed_ids = [r["node_id"] for r in analyzed_reports if "node_id" in r]
        remaining_to_analyze = [n for n in failures if n not in analyzed_ids]
        
        recent_history = self.memory["history"]

        context_data = {
            "current_state": self.state.value,
            "past_actions": recent_history,
            "failed_nodes": failures,          #λειτουργία με memory
            "remaining_to_analyze": remaining_to_analyze,
            "impact_reports": analyzed_reports,
            "available_crews": available_crews,
        }
        
        user_context = json.dumps(context_data, indent=2)
        system_prompt = self.get_system_prompt()

        # Απαίτηση της εκφώνησης: Εκτύπωση του Prompt
        print(f"[PROMPT]: {system_prompt}\nCONTEXT DATA: {user_context}")
        
        # 2. THINK: Call LLM
        decision = llm_call(system_prompt, user_context)
        
        # Απαίτηση της εκφώνησης: Εκτύπωση του Raw LLM output
        print(f"[RAW LLM]: {json.dumps(decision, indent=2)}")
        
        action = decision.get("action", "none")
        args = decision.get("arguments", {})
        thought = decision.get("thought", "No reasoning provided")
        next_state_str = decision.get("next_state", self.state.value)
        
        # 3. ACT: Execute the chosen tool dynamically
        observation = {}
        if action == "detect_failure_nodes":
            observation = toolList.detect_failure_nodes()
            self.memory["context"]["failures"] = observation
        
        elif action == "estimate_impact":
            node_id = args.get("node_id")
            if node_id:
                observation = toolList.estimate_impact(node_id)
                self.memory["context"].setdefault("impact_reports", []).append(observation)
            else:
                observation = {"error": "Missing node_id argument"}
        
        elif action == "assign_repair_crew":
            node_ids = args.get("node_ids", [])
            crew_ids = args.get("crew_ids", [])
            observation = toolList.assign_repair_crew(node_ids, crew_ids)

        # Απαίτηση της εκφώνησης: Εκτύπωση του Observation
        print(f"[OBSERVATION]: {observation}")
        
        # DYNAMIC TRANSITION: Update state based on LLM's choice
        try:
            self.state = AgentState(next_state_str)
        except ValueError:
            print(f"[WARNING] Invalid next_state '{next_state_str}' returned by LLM. Maintaining current state.")

        # Memory Management (Sliding Window)
        self.memory["history"].append({
            "step": self.step_count, 
            "state": self.state.value,
            "action": action, 
            "observation": observation
        })
        if len(self.memory["history"]) > 8: #αποθηκεύονται μόνο 5 προηγούμενα steps
            self.memory["history"] = self.memory["history"][-8:]

    def run(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = os.path.join(config.runs_path, f"run_log_{ts}.txt")

        class DualLogger:
            def __init__(self, filepath):
                self.terminal = sys.stdout
                self.log = open(filepath, "w", encoding="utf-8")
            def write(self, message):
                self.terminal.write(message)
                self.log.write(message)
            def flush(self):
                self.terminal.flush()
                self.log.flush()
            def close(self):
                self.log.close()

        original_stdout = sys.stdout
        sys.stdout = DualLogger(log_filename)
        
        try:
            print("--- INFRASTRUCTURE AGENT STARTED ---")
            
            while self.state != AgentState.FINAL and self.step_count < self.max_steps:
                self.step()
                time.sleep(1)

            print("\n--- AGENT FINISHED ---")
            print("Final World State:")
            print(json.dumps(config.WORLD_STATE["nodes"], indent=2))
        finally:
            sys.stdout.close()
            sys.stdout = original_stdout
            
        print(f"\n Το Log αποθηκεύτηκε στο αρχείο: {log_filename}")

if __name__ == "__main__":
    scenario_files = jsonPicker.get_available_scenarios()
    print(f"Found {len(scenario_files)} scenarios to run.")

    for scenario_path in scenario_files:
        scenario_name = os.path.basename(scenario_path)
        print(f"\n{'▬'*50}\nRUNNING SCENARIO: {scenario_name}\n{'▬'*50}")
        
        config.WORLD_STATE.clear()
        config.WORLD_STATE.update(jsonPicker.load_world_state(scenario_path))
        
        agent = InfrastructureAgent(max_steps=15)
        agent.run()