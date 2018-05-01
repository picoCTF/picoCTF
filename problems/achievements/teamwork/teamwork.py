def process(api, data):
    members = api.team.get_team_members(tid=data["tid"])
    if len(members) < 2:
        earned = False
    else:
        earned = True
        for member in members:
            if api.problem.count_submissions(uid=member["uid"], correctness=True) < 1:
                earned = False
                break
    return earned, {}
