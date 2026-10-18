import json, os
from qiskit import transpile

# Load token directly (raw string to avoid escape issues)
token_path = r"D:\codex\browser-native-ai-system\Quantum Delayed Synchronization\ibm_token.json"
with open(token_path) as f:
    creds = json.load(f)
token = creds["apikey"]
print(f"Token loaded (len={len(token)})")

# Try direct backend access
try:
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService(channel="ibm_quantum", token=token)
    backend = service.get_backend("ibm_kingston")
    print(f"Backend: ibm_kingston")
    props = backend.qubit_properties(91)
    print(f"Qubit 91: T1={props.t1*1e6:.1f}us T2={props.t2*1e6:.1f}us")
except AttributeError as e:
    print(f"Pydantic issue: {e}")
    print("Trying qiskit-ibm-provider legacy...")
    try:
        from qiskit_ibm_provider import IBMProvider
        provider = IBMProvider(token=token)
        backend = provider.get_backend("ibm_kingston")
        print(f"Legacy backend OK: ibm_kingston")
    except ImportError:
        print("qiskit-ibm-provider not installed")
    except Exception as e2:
        print(f"Legacy also failed: {e2}")
except Exception as e:
    print(f"Error: {e}")
