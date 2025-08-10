#!/usr/bin/env python3
"""
Test script to verify Browser Use installation
"""
import asyncio
import sys
from pathlib import Path

async def test_installation():
    """Test the Browser Use installation."""
    
    print("🔍 Testing Browser Use installation...\n")
    
    # Test 1: Import basic modules
    print("1. Testing module imports...")
    try:
        from browser_use import Agent
        from browser_use.llm import ChatOpenAI
        from dotenv import load_dotenv
        print("✅ All required modules imported successfully")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test 2: Check environment variables
    print("\n2. Checking environment variables...")
    import os
    load_dotenv()
    
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    
    if has_openai:
        print("✅ OpenAI API key found")
    else:
        print("⚠️  OpenAI API key not found (set OPENAI_API_KEY in .env)")
    
    if has_anthropic:
        print("✅ Anthropic API key found")
    else:
        print("⚠️  Anthropic API key not found (set ANTHROPIC_API_KEY in .env)")
    
    # Test 3: Check Playwright installation
    print("\n3. Checking Playwright installation...")
    try:
        import playwright
        print("✅ Playwright module found")
        
        # Check if browsers are installed
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print("✅ Chromium browser available")
            except Exception as e:
                print(f"⚠️  Chromium browser not available: {e}")
                print("   Run: playwright install chromium")
    except ImportError:
        print("❌ Playwright not installed")
        return False
    
    # Test 4: Simple agent creation (without running)
    print("\n4. Testing agent creation...")
    if has_openai or has_anthropic:
        try:
            if has_openai:
                llm = ChatOpenAI(model="gpt-4o")
            else:
                # You would need to import and use Anthropic here
                print("⚠️  Using OpenAI for test (Anthropic key found but not tested)")
                llm = ChatOpenAI(model="gpt-4o")
            
            agent = Agent(
                task="Test task",
                llm=llm,
                use_vision=True
            )
            print("✅ Agent created successfully")
        except Exception as e:
            print(f"❌ Failed to create agent: {e}")
            return False
    else:
        print("⚠️  Skipping agent creation test (no API keys found)")
    
    print("\n" + "="*50)
    print("Installation test completed!")
    print("="*50)
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_installation())
    sys.exit(0 if success else 1)