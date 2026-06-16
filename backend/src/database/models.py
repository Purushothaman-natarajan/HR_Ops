"""SQLAlchemy ORM models for the HR Ops database."""

from sqlalchemy import Column, Float, ForeignKey, Integer, String

from backend.src.database.connection import Base


class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column("Employee_ID", String, primary_key=True)
    name = Column("Employee_Name", String, nullable=False)
    age = Column("Age", Integer, default=0)
    country = Column("Country", String, default="")
    department = Column("Department", String, default="General")
    position = Column("Position", String, default="Staff")
    salary = Column("Salary", Float, default=0.0)
    joining_date = Column("Joining_Date", String, default="")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.Employee_ID"), nullable=False)
    date = Column(String, nullable=False)
    status = Column(String, nullable=False)
    hours_worked = Column(Float, default=0)


class Payroll(Base):
    __tablename__ = "payroll"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.Employee_ID"), nullable=False)
    pay_period = Column(String, nullable=False)
    gross_pay = Column(Float, nullable=False)
    deductions = Column(Float, default=0)
    net_pay = Column(Float, nullable=False)
    payment_date = Column(String, default="")


class Leave(Base):
    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.Employee_ID"), nullable=False)
    leave_type = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    status = Column(String, default="Pending")
    reason = Column(String, default="")


class Performance(Base):
    __tablename__ = "performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.Employee_ID"), nullable=False)
    review_date = Column(String, nullable=False)
    rating = Column(Float, nullable=False)
    comments = Column(String, default="")
    reviewer = Column(String, default="System")


ALL_MODELS = [Employee, Attendance, Payroll, Leave, Performance]
