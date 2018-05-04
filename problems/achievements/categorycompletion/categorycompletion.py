def process(api, data):
    pid = data["pid"]
    pid_map = api.stats.get_pid_categories()
    category = pid_map[pid]
    category_pids = api.stats.get_pids_by_category()[category]
    solved_pids = api.problem.get_solved_pids(tid=data['tid'])

    earned = True
    for pid in category_pids:
        if pid not in solved_pids:
            earned = False

    name = "Category Master"
    if category == "Cryptography":
        name = "Cryptography Experts"
    elif category == "Reverse Engineering":
        name = "Reversing Champions"
    elif category == "Binary Exploitation":
        name = "Binary Masters"
    elif category == "Forensics":
        name = "Great Detectives"
    elif category == "Web Exploitation":
        name = "Masters of the Web"
    elif category == "Master Challenge":
        name = "Best of the Best"
    elif category == "Miscellaneous":
        name = "Any Dream Will Do"

    description = "Solved every '%s' challenge" % category
    return earned, {"name": name, "description": description}
