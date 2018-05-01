def process(api, data):
    pid_map = api.stats.get_pid_categories()
    solved_pids = api.problem.get_solved_pids(tid=data['tid'])
    categories = set()
    for pid in solved_pids:
        categories.add(pid_map[pid])
    earned = True
    for cat in api.problem.get_all_categories():
        if cat not in categories:
            if cat != "Master Challenge":
                earned = False
                break
    return earned, {}
