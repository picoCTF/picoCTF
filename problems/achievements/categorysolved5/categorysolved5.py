def process(api, data):
    pid = data["pid"]
    pid_map = api.stats.get_pid_categories()
    category = pid_map[pid]
    category_pids = api.stats.get_pids_by_category()[category]
    solved_pids = api.problem.get_solved_pids(tid=data['tid'])

    solve_count = 0
    for pid in category_pids:
        if pid in solved_pids:
            solve_count += 1

    earned = solve_count == 5

    name = "Investigating In-Depth"
    if category == "Cryptography":
        name = "Crypto Specialists"
    elif category == "Reverse Engineering":
        name = "Reversing Engineers"
    elif category == "Binary Exploitation":
        name = "Assembly Wizards"
    elif category == "Forensics":
        name = "In-Depth Investigation"
    elif category == "Web Exploitation":
        name = "Web Warriors"
    elif category == "Master Challenge":
        earned = False
    elif category == "Miscellaneous":
        earned = False

    description = "Solved 5 '%s' challenges" % category
    return earned, {"name": name, "description": description}
