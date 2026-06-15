import json

def format_tool_result_to_markdown(tool_result: dict) -> str:
    """Format tool execution results (especially database queries) into clean Markdown."""
    if not isinstance(tool_result, dict):
        return str(tool_result)
        
    tool_name = tool_result.get("tool", "")
    result = tool_result.get("result", {})
    
    if not isinstance(result, dict):
        # Handle cases where result might not be a dict
        if isinstance(result, list):
            return f"### Tool Result (`{tool_name}`)\n\n" + "\n".join(f"- {item}" for item in result)
        return f"### Tool Result (`{tool_name}`)\n\n{result}"
        
    # Check if this is a db query result
    if tool_name == "execute_db_query":
        if not result.get("success"):
            return f"### Database Query Error\n\n**Error:** {result.get('error', 'Unknown error')}"
            
        q_type = result.get("type", "read")
        if q_type == "write":
            return f"### Database Update Successful\n\n{result.get('message', '')}"
            
        # Read query
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        row_count = result.get("row_count", 0)
        
        if not rows:
            return "### Database Query Results\n\nNo records found matching the query."
            
        # Generate Markdown Table
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        md_rows = []
        for r in rows:
            row_vals = [str(r.get(col, "")) if r.get(col) is not None else "" for col in columns]
            md_rows.append("| " + " | ".join(row_vals) + " |")
            
        table_md = "\n".join([header, separator] + md_rows)
        summary = f"### Database Query Results ({row_count} row{'s' if row_count != 1 else ''})\n\n{table_md}"
        return summary
        
    # Check if this is lookup_employee result
    if tool_name == "lookup_employee":
        emp = result
        if not isinstance(emp, dict) or "employee_id" not in emp:
            return f"### Employee Lookup Result\n\n```json\n{json.dumps(result, indent=2)}\n```"
            
        md = f"### Employee Profile: {emp.get('name', 'N/A')} ({emp.get('employee_id')})\n\n"
        md += f"- **Department:** {emp.get('department', 'N/A')}\n"
        if "salary" in emp:
            try:
                salary_val = float(emp.get("salary") or 0)
                md += f"- **Salary:** ${salary_val:,.2f}\n"
            except (ValueError, TypeError):
                md += f"- **Salary:** {emp.get('salary')}\n"
        if "leave_balance" in emp:
            md += f"- **Leave Balance:** {emp.get('leave_balance', 0)} days\n"
        if "compliance_status" in emp:
            md += f"- **Compliance Status:** {emp.get('compliance_status', 'compliant')}\n"
            
        # Include other fields dynamically if they exist (leaves, work_location, etc.)
        for k, v in emp.items():
            if k not in ["employee_id", "name", "department", "salary", "leave_balance", "compliance_status"]:
                title = k.replace("_", " ").title()
                md += f"- **{title}:** {v}\n"
        return md
        
    # Check if this is modify_record
    if tool_name == "modify_record":
        if result.get("success"):
            return f"### Record Update Successful\n\n{result.get('message', '')}"
        else:
            return f"### Record Update Failed\n\n{result.get('message', '')}"
            
    # Check if this is escalate_to_human
    if tool_name == "escalate_to_human":
        ticket_id = result.get("ticket_id", "N/A")
        status = result.get("status", "N/A")
        timestamp = result.get("timestamp", "N/A")
        return f"### Escalation Ticket Created\n\n- **Ticket ID:** `{ticket_id}`\n- **Status:** {status}\n- **Timestamp:** {timestamp}"
        
    # General fallback
    return f"### Tool Execution Result (`{tool_name}`)\n\n```json\n{json.dumps(result, indent=2)}\n```"
