import sqlite3, statistics

conn = sqlite3.connect("backend/data/hr_ops.db")
cur = conn.cursor()

# 1. Attendance status distribution
cur.execute("SELECT status, count(*) FROM attendance GROUP BY status")
print("=== Attendance statuses ===")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# 2. Employees with high absence rate
cur.execute("""
    SELECT e.Employee_ID, e.Employee_Name, e.Department,
           COUNT(a.id) as total_days,
           SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) as absent_days,
           ROUND(100.0*SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END)/COUNT(a.id),1) as absence_pct
    FROM employees e
    JOIN attendance a ON e.Employee_ID = a.employee_id
    GROUP BY e.Employee_ID
    HAVING total_days >= 10 AND absence_pct > 15
    ORDER BY absence_pct DESC
    LIMIT 10
""")
print("\n=== High absence rate (>15%) ===")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1][:20]:<20} {r[2]:<15} total={r[3]} absent={r[4]} ({r[5]}%)")

# 3. Employees with NO attendance records at all
cur.execute("""
    SELECT e.Employee_ID, e.Employee_Name, e.Department, e.Joining_Date
    FROM employees e
    LEFT JOIN attendance a ON e.Employee_ID = a.employee_id
    WHERE a.id IS NULL
    LIMIT 10
""")
print("\n=== Employees with ZERO attendance records ===")
for r in cur.fetchall():
    print(f"  {r}")

# 4. Summary absence stats
cur.execute("""
    SELECT 
        ROUND(100.0*SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END)/COUNT(a.id),2) as avg_absence_pct,
        MAX(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) as has_absent
    FROM attendance a
""")
r = cur.fetchone()
print(f"\n=== Overall absence rate: {r[0]}% ===")

# 5. Late arrival pattern
cur.execute("""
    SELECT e.Employee_ID, e.Employee_Name, e.Department,
           COUNT(a.id) as total_days,
           SUM(CASE WHEN a.status='Late' THEN 1 ELSE 0 END) as late_days,
           ROUND(100.0*SUM(CASE WHEN a.status='Late' THEN 1 ELSE 0 END)/COUNT(a.id),1) as late_pct
    FROM employees e
    JOIN attendance a ON e.Employee_ID = a.employee_id
    GROUP BY e.Employee_ID
    HAVING total_days >= 10 AND late_pct > 15
    ORDER BY late_pct DESC
    LIMIT 10
""")
print("\n=== Chronic late arrivals (>15% days late) ===")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1][:20]:<20} {r[2]:<15} late={r[4]}/{r[3]} ({r[5]}%)")

conn.close()
