import pytest
from backend.src.repositories.queries import query_performance
from backend.src.repositories.models import Performance, Base
from backend.src.repositories.connection import SessionLocal, engine

@pytest.fixture
def clean_session():
    """Yield a database session and clean up any test data inserted during the test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    # Keep track of employee IDs to delete from Performance (we won't touch employees table)
    test_employees = []

    class TestSessionWrapper:
        def __init__(self, s):
            self.s = s

        def add(self, instance):
            if isinstance(instance, Performance) and instance.employee_id not in test_employees:
                test_employees.append(instance.employee_id)
            self.s.add(instance)

        def add_all(self, instances):
            for i in instances:
                if isinstance(i, Performance) and i.employee_id not in test_employees:
                    test_employees.append(i.employee_id)
            self.s.add_all(instances)

        def commit(self):
            self.s.commit()

        def __getattr__(self, name):
            return getattr(self.s, name)

    wrapper = TestSessionWrapper(session)
    yield wrapper

    # Cleanup after test
    for eid in test_employees:
        session.query(Performance).filter(Performance.employee_id == eid).delete()
    session.commit()
    session.close()


def test_query_performance_empty(clean_session):
    """Test that query_performance returns an empty list for an employee without records."""
    # Check an employee that does not exist
    result = query_performance("EMP_NONEXISTENT")
    assert result == []

def test_query_performance_with_data(clean_session):
    """Test that query_performance correctly fetches and formats performance records."""
    emp_id = "TEST_EMP_PERF_1"

    perf1 = Performance(employee_id=emp_id, review_date="2023-01-01", rating=4.5, comments="Good", reviewer="Manager A")
    perf2 = Performance(employee_id=emp_id, review_date="2024-01-01", rating=5.0, comments="Excellent", reviewer="Manager B")
    clean_session.add_all([perf1, perf2])
    clean_session.commit()

    result = query_performance(emp_id)
    assert len(result) == 2

    # Ensure ordered by descending review_date
    assert result[0]["rating"] == 5.0
    assert result[0]["review_date"] == "2024-01-01"
    assert result[0]["comments"] == "Excellent"
    assert result[0]["reviewer"] == "Manager B"
    assert result[0]["employee_id"] == emp_id
    assert "id" in result[0]

    assert result[1]["rating"] == 4.5
    assert result[1]["review_date"] == "2023-01-01"

def test_query_performance_limit(clean_session):
    """Test that query_performance respects the limit parameter."""
    emp_id = "TEST_EMP_PERF_2"

    # Add 10 performance records
    perfs = []
    for i in range(10):
        # Format the month to be 2 digits to ensure correct alphabetical sorting
        month = f"{i+1:02d}"
        perfs.append(Performance(employee_id=emp_id, review_date=f"2023-{month}-01", rating=3.0 + (i * 0.1)))
    clean_session.add_all(perfs)
    clean_session.commit()

    # Query with limit 3
    result = query_performance(emp_id, limit=3)
    assert len(result) == 3

    # Ensure it's the top 3 most recent
    assert result[0]["review_date"] == "2023-10-01"
    assert result[1]["review_date"] == "2023-09-01"
    assert result[2]["review_date"] == "2023-08-01"
