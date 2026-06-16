import sys
sys.path.insert(0, ".")

from backend.src.agents.nodes.action_node import _prescreen_query
from backend.src.tools.api_mocks import search_employee_by_name

# Test pre-screener
tests = [
    "Find JOHN and his info",
    "Find john",
    "Show me Alice Chen profile",
    "Who is Bob Smith",
    "lookup EMP0001",
    "How many employees are there",
    "What is the leave policy",
]
print("=== Pre-screener tests ===")
for q in tests:
    r = _prescreen_query(q)
    print(f"  Q: {repr(q)}")
    print(f"  -> {r}")
    print()

# Test search tool
print("=== search_employee_by_name('John') ===")
result = search_employee_by_name("John")
found = result.get("found")
count = result.get("count")
print(f"found={found} count={count}")
if result.get("employees"):
    for emp in result["employees"][:3]:
        eid = emp.get("Employee_ID")
        name = emp.get("Employee_Name")
        dept = emp.get("Department")
        pos = emp.get("Position")
        rem = emp.get("leaves_remaining")
        print(f"  {eid} | {name} | {dept} | {pos} | remaining={rem}")
