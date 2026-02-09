from utils.llm_client import LLMClient

client = LLMClient()
try:
    response = client.generate("Say 'Hello, Job Agent is working!' in 5 words.")
    print(f"✓ LLM Response: {response}")
except Exception as e:
    print(f"✗ Error: {e}")