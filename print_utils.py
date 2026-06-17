"""
Printing utilities for formatting and preparing print jobs
"""

ESC = '\x1b'  # Escape character

def cut_paper():
    """Generate ESC/POS command for full paper cut"""
    return '\x1d\x56\x42\x36'  # GS V B 54 (feed 54/180 inch and cut)


def format_shopping_list(title, items):
    from datetime import datetime

    output = ""
    output += '\n\n'

    # Title (bold)
    output += ESC + 'E' + chr(1)
    output += title or "Shopping List"
    output += ESC + 'E' + chr(0)
    output += '\n'

    # Date
    output += datetime.now().strftime('%d.%m.%Y %H:%M')
    output += '\n'

    output += '-' * 32 + '\n'

    for item in items:
        if item and item.strip():
            output += '[ ] ' + item.strip() + '\n'

    output += '-' * 32 + '\n'
    output += f'{len(items)} items\n'
    output += '\n\n'

    return output + cut_paper()

def format_section(todo, assignee, deadline):
    output = ""
    output += '\n\n'

    # Deadline
    output += deadline + '\n'

    # Small spacing
    output += ESC + '3' + chr(18)
    output += '\n'
    output += ESC + '2'

    # Todo (bold)
    output += ESC + 'E' + chr(1)
    output += todo
    output += ESC + 'E' + chr(0)
    output += '\n'

    # Small spacing
    output += ESC + '3' + chr(18)
    output += '\n'
    output += ESC + '2'

    # Assignee
    if assignee:
        output += '@' + assignee + '\n'

    output += '\n\n'

    return output + cut_paper()

def init_printer():
    return ESC + '@'

def create_print_job(sections):
    print_data = init_printer().encode('utf-8')
    for section in sections:
        todo = section.get('todo', '')
        assignee = section.get('assignee', '')
        deadline = section.get('deadline', '')
        print_data += format_section(todo, assignee, deadline).encode('utf-8')
    return print_data

def validate_sections(sections):
    if not isinstance(sections, list):
        return False, "Sections must be a list"
    if not sections:
        return False, "No sections provided"
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            return False, f"Section {i} must be a dictionary"
        if 'todo' not in section:
            return False, f"Section {i} must have a 'todo' field"
    return True, None
