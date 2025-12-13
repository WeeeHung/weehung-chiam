"""
Main Entry Point: Agentic AI Application

This is the main entry point that orchestrates the agent workflow:
1. Receive user input
2. (Optional) Retrieve relevant memory
3. Plan sub-tasks
4. Execute tasks (call Gemini API and tools)
5. Generate final response
"""

import sys
from planner import Planner
from executor import Executor
from memory import Memory


class Agent:
    """
    Main Agent class that orchestrates the agentic workflow.
    """
    
    def __init__(self):
        """Initialize the agent with all core modules."""
        self.planner = Planner()
        self.executor = Executor()
        self.memory = Memory()
    
    def process(self, user_input: str) -> str:
        """
        Process user input through the complete agent workflow.
        
        Args:
            user_input: The user's request or question
            
        Returns:
            Final response string
        """
        print(f"📥 Received input: {user_input}\n")
        
        # Step 1: (Optional) Retrieve relevant memory
        print("🔍 Retrieving relevant memory...")
        relevant_memory = self.memory.retrieve(user_input, limit=3)
        context = {"memory": relevant_memory} if relevant_memory else {}
        print(f"   Found {len(relevant_memory)} relevant past interactions\n")
        
        # Step 2: Plan sub-tasks
        print("📋 Planning sub-tasks...")
        tasks = self.planner.plan(user_input, context)
        print(f"   Generated {len(tasks)} task(s)\n")
        
        # Step 3: Execute tasks
        print("⚙️  Executing tasks...")
        results = []
        for i, task in enumerate(tasks, 1):
            print(f"   Task {i}/{len(tasks)}: {task.get('task', 'Unknown')}")
            result = self.executor.execute(task, context)
            if result["success"]:
                results.append(result["result"])
                print(f"   ✓ Task {i} completed\n")
            else:
                print(f"   ✗ Task {i} failed: {result['error']}\n")
                results.append(f"Error: {result['error']}")
        
        # Step 4: Generate final response
        print("📤 Generating final response...")
        final_response = "\n".join(results) if results else "No results generated."
        
        # Step 5: Store interaction in memory
        self.memory.store({
            "input": user_input,
            "output": final_response,
            "metadata": {
                "tasks_count": len(tasks),
                "success": all(r and not r.startswith("Error:") for r in results)
            }
        })
        
        print("✓ Interaction stored in memory\n")
        return final_response


def main():
    """Main function to run the agent."""
    print("=" * 60)
    print("🤖 Agentic AI Application")
    print("=" * 60)
    print()
    
    agent = Agent()
    
    # Interactive mode
    if len(sys.argv) > 1:
        # Command-line argument mode
        user_input = " ".join(sys.argv[1:])
        response = agent.process(user_input)
        print("=" * 60)
        print("📝 Response:")
        print("=" * 60)
        print(response)
    else:
        # Interactive REPL mode
        print("Enter your queries (type 'exit' or 'quit' to end):\n")
        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                response = agent.process(user_input)
                print("\n" + "=" * 60)
                print("🤖 Agent:")
                print("=" * 60)
                print(response)
                print()
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    main()

