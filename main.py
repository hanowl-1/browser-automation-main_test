#!/usr/bin/env python3
"""
Basic Browser Use Agent Implementation
This script demonstrates a simple browser automation agent using Browser Use.
"""

from browser_use.llm import ChatOpenAI
from browser_use import Agent
from dotenv import load_dotenv
import asyncio
import sys
from typing import Optional

# Load environment variables
load_dotenv()


async def run_simple_task(task: str) -> Optional[str]:
    """
    Run a simple browser automation task.
    
    Args:
        task: The task description for the agent to execute
        
    Returns:
        The result from the agent execution
    """
    try:
        # Initialize the LLM
        llm = ChatOpenAI(model="gpt-4o")
        
        # Create the agent
        agent = Agent(
            task=task,
            llm=llm,
            use_vision=True,  # Enable visual processing
            vision_detail_level='auto'  # Automatic detail level
        )
        
        # Run the agent
        print(f"🚀 Starting task: {task}")
        print("⏳ Agent is working...")
        
        result = await agent.run()
        
        print("✅ Task completed successfully!")
        return result
        
    except Exception as e:
        print(f"❌ Error executing task: {e}")
        return None


async def main():
    """Main function to run browser automation tasks."""
    
    # Example tasks - you can modify these or pass as command line arguments
    example_tasks = [
        "Search for the latest news about artificial intelligence on Google",
        "Find the current price of Bitcoin",
        "Check the weather forecast for New York City",
        "Compare prices of iPhone 15 Pro on different websites",
    ]
    
    # Check if a task was provided as command line argument
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        print("Available example tasks:")
        for i, task in enumerate(example_tasks, 1):
            print(f"{i}. {task}")
        
        choice = input("\nEnter task number (1-4) or type your own task: ").strip()
        
        if choice.isdigit() and 1 <= int(choice) <= len(example_tasks):
            task = example_tasks[int(choice) - 1]
        else:
            task = choice if choice else example_tasks[0]
    
    # Run the task
    result = await run_simple_task(task)
    
    if result:
        print("\n📊 Result:")
        print("-" * 50)
        print(result)
        print("-" * 50)


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())