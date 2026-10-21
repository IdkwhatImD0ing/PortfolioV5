
import os
os.environ["PINECONE_API_KEY"] = "test"
os.environ["OPENAI_API_KEY"] = "test"
os.environ["RETELL_API_KEY"] = "test"

from agents import InputGuardrailTripwireTriggered

print(f"InputGuardrailTripwireTriggered bases: {InputGuardrailTripwireTriggered.__bases__}")
try:
    raise InputGuardrailTripwireTriggered({"output": {}})
except Exception:
    print("Caught by Exception")
except BaseException:
    print("Caught by BaseException")
