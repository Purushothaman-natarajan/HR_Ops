"""End-to-end test: generate queries per policy, test retrieval + generation for both modes."""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.src.memory.vector_store import similarity_search, get_document_count
from backend.src.services.conversation_service import session_store

# ── Test queries per policy document ──────────────────────────────────────────

TEST_QUERIES = {
    "leave_policy": [
        "How many annual leave days do I get per month?",
        "When is a medical certificate required for sick leave?",
        "How long is maternity leave and is it paid?",
    ],
    "attendance_policy": [
        "What are the core working hours when everyone must be available?",
        "How many remote work days per week are allowed?",
        "What happens if I have too many unscheduled absences?",
    ],
    "compensation_policy": [
        "What is the range for merit salary increases?",
        "How much is the referral bonus?",
        "Do retroactive salary adjustments require special approval?",
    ],
    "compliance_policy": [
        "How often must employees complete compliance training?",
        "What is the data retention period after employment ends?",
        "How much notice is required for voluntary termination?",
    ],
}

EXPECTED_SOURCES = {
    "How many annual leave days do I get per month?": "leave_policy",
    "When is a medical certificate required for sick leave?": "leave_policy",
    "How long is maternity leave and is it paid?": "leave_policy",
    "What are the core working hours when everyone must be available?": "attendance_policy",
    "How many remote work days per week are allowed?": "attendance_policy",
    "What happens if I have too many unscheduled absences?": "attendance_policy",
    "What is the range for merit salary increases?": "compensation_policy",
    "How much is the referral bonus?": "compensation_policy",
    "Do retroactive salary adjustments require special approval?": "compensation_policy",
    "How often must employees complete compliance training?": "compliance_policy",
    "What is the data retention period after employment ends?": "compliance_policy",
    "How much notice is required for voluntary termination?": "compliance_policy",
}

# ── Expected answers (ground truth from policy docs) ──────────────────────────

EXPECTED_ANSWERS = {
    "How many annual leave days do I get per month?": "2.5 days",
    "When is a medical certificate required for sick leave?": "3 consecutive",
    "How long is maternity leave and is it paid?": "26 weeks",
    "What are the core working hours when everyone must be available?": "10:00 AM to 4:00 PM",
    "How many remote work days per week are allowed?": "3 days",
    "What happens if I have too many unscheduled absences?": "review",
    "What is the range for merit salary increases?": "3% to 10%",
    "How much is the referral bonus?": "$3,000",
    "Do retroactive salary adjustments require special approval?": "compliance sign-off",
    "How often must employees complete compliance training?": "annual",
    "What is the data retention period after employment ends?": "7 years",
    "How much notice is required for voluntary termination?": "2 weeks",
}


def test_retrieval():
    """Test 1: Verify similarity search returns correct policy documents."""
    print("\n" + "=" * 80)
    print("TEST 1: RETRIEVAL ACCURACY")
    print("=" * 80)

    doc_count = get_document_count("hr_policies")
    print(f"\nVector store document count: {doc_count}")

    results = []
    total = 0
    correct = 0

    for policy_id, queries in TEST_QUERIES.items():
        for query in queries:
            total += 1
            docs = similarity_search(query, k=3, collection_name="hr_policies")
            sources = [d.metadata.get("policy", d.metadata.get("source", "unknown")) for d in docs]
            expected_source = EXPECTED_SOURCES.get(query, policy_id)
            hit = expected_source in sources

            status = "PASS" if hit else "FAIL"
            if hit:
                correct += 1

            print(f"\n  [{status}] Query: {query}")
            print(f"         Expected source: {expected_source}")
            print(f"         Retrieved: {sources[:3]}")
            results.append({"query": query, "expected": expected_source, "retrieved": sources, "hit": hit})

    accuracy = (correct / total) * 100 if total > 0 else 0
    print(f"\n  Retrieval accuracy: {correct}/{total} ({accuracy:.0f}%)")
    return results, accuracy


async def test_generation(mode: str, queries: list[str]):
    """Test 2: Run full pipeline for a set of queries in the given mode."""
    print(f"\n{'=' * 80}")
    print(f"TEST 2: GENERATION ({mode.upper()} MODE)")
    print(f"{'=' * 80}")

    results = []
    total = 0
    grounded = 0

    for query in queries:
        total += 1
        expected_answer = EXPECTED_ANSWERS.get(query, "")
        print(f"\n  Query: {query}")
        print(f"  Expected keyword: '{expected_answer}'")

        start = time.time()
        try:
            session = session_store.create_session(query, mode=mode)
            result = await session_store.run_turn_async(session["session_id"], query)
            elapsed = (time.time() - start) * 1000

            response = result.get("response", "")
            trace_count = len(result.get("trace_events", []))
            cost = result.get("total_cost_usd", 0)

            # Check grounding: does the response contain the expected keyword?
            is_grounded = expected_answer.lower() in response.lower() if expected_answer else False
            if is_grounded:
                grounded += 1

            status = "PASS" if is_grounded else "FAIL"
            print(f"  [{status}] Response ({elapsed:.0f}ms, ${cost:.5f}, {trace_count} trace events):")
            # Print first 200 chars of response
            preview = response[:200].replace("\n", " ")
            print(f"         {preview}...")

            # Show trace nodes
            trace_nodes = [t.get("node", "?") for t in result.get("trace_events", [])]
            print(f"         Trace path: {' -> '.join(trace_nodes)}")

            results.append({
                "query": query,
                "response": response,
                "grounded": is_grounded,
                "elapsed_ms": elapsed,
                "cost": cost,
                "trace_nodes": trace_nodes,
            })

            # Clean up session
            session_store.delete_session(session["session_id"])

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            print(f"  [ERROR] {e} ({elapsed:.0f}ms)")
            results.append({"query": query, "response": "", "grounded": False, "error": str(e)})

    accuracy = (grounded / total) * 100 if total > 0 else 0
    print(f"\n  Generation grounding: {grounded}/{total} ({accuracy:.0f}%)")
    return results, accuracy


async def main():
    print("\n" + "#" * 80)
    print("# HR Buddy — Retrieval & Generation Test Suite")
    print("#" * 80)

    # ── Test 1: Retrieval ──
    retrieval_results, retrieval_accuracy = test_retrieval()

    # ── Test 2: Standard mode generation ──
    all_queries = [q for queries in TEST_QUERIES.values() for q in queries]
    standard_results, standard_accuracy = await test_generation("standard", all_queries)

    # ── Test 3: Advanced mode generation ──
    advanced_results, advanced_accuracy = await test_generation("advanced", all_queries)

    # ── Summary ──
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n  Retrieval accuracy:       {retrieval_accuracy:.0f}%")
    print(f"  Standard mode grounding:  {standard_accuracy:.0f}%")
    print(f"  Advanced mode grounding:  {advanced_accuracy:.0f}%")
    print()

    # ── Per-query breakdown ──
    print("  Per-query breakdown:")
    print(f"  {'Query':<55} {'Retrieval':>10} {'Standard':>10} {'Advanced':>10}")
    print(f"  {'-'*55} {'-'*10} {'-'*10} {'-'*10}")

    for policy_id, queries in TEST_QUERIES.items():
        for query in queries:
            short_q = query[:52] + "..." if len(query) > 55 else query
            ret = next((r["hit"] for r in retrieval_results if r["query"] == query), None)
            std = next((r["grounded"] for r in standard_results if r["query"] == query), None)
            adv = next((r["grounded"] for r in advanced_results if r["query"] == query), None)
            ret_s = "PASS" if ret else "FAIL"
            std_s = "PASS" if std else "FAIL"
            adv_s = "PASS" if adv else "FAIL"
            print(f"  {short_q:<55} {ret_s:>10} {std_s:>10} {adv_s:>10}")

    print()
    overall_pass = retrieval_accuracy >= 80 and standard_accuracy >= 60 and advanced_accuracy >= 60
    print(f"  Overall: {'ALL TESTS PASSED' if overall_pass else 'SOME TESTS FAILED'}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
