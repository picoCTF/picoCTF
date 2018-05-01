def process(api, data):
    """
    Breakthroughs are rewarded to the first team to solve a given problem.

    Data Required: tid, pid
    """

    submission_count = api.problem.count_submissions(pid=data["pid"], correctness=True, eligibility=True)
    if submission_count == 1:
        submissions = api.problem.get_submissions(pid=data["pid"], correctness=True, eligibility=True)
        problem = api.problem.get_problem(pid=data["pid"])
        valid = submissions[0]['tid'] == data['tid']
        return valid, {
            "name": "Breakthrough!".format(problem["name"]),
            "description": "Your team was the first team to solve {}.".format(problem["name"])
        }
    else:
        return False, {}
