"""
Fabricate user data and activity for demo and testing purposes.
"""

import random
import sys

import api

random.seed(0xd3adb333f)

content = open(sys.argv[1], "r").readlines()
data = [line.split(",") for line in content[1:]]

group_names = ["Course %s" % i for i in range(6)]

admin_tid = api.team.create_team({
    "team_name": "admin",
    "password": "password",
    "eligibile": True
})
admin_uid = api.user.create_user(
    "admin",
    "admin",
    "admin",
    "admin@test.com",
    api.common.hash_password("password"),
    admin_tid,
    admin=True,
    teacher=True)

admin = api.user.get_user(name="admin")

print("Created admin user")

groups = []
for group_name in group_names:
    gid = api.group.create_group(admin["tid"], group_name)
    groups.append(api.group.get_group(gid=gid))
    print("Created group: " + group_name)

for (firstname, lastname, email, username, _) in data[:100]:
    user_data = {
        "username": username,
        "password": "password",
        "firstname": firstname,
        "lastname": lastname,
        "email": email,
        "eligibility": "eligible"
        if bool(random.randint(0, 1)) else "ineligible",
        "affiliation": "Test"
    }
    uid = api.user.create_simple_user_request(user_data)

    user = api.user.get_user(uid=uid)
    team = api.user.get_team(uid=uid)

    api.group.join_group(random.choice(groups)["gid"], team["tid"])

queue = sum(
    [[user] * random.randint(0, 60) for user in api.user.get_all_users()], [])
random.shuffle(queue)
for user in queue:
    team = api.user.get_team(uid=user["uid"])
    unlocked = [
        api.problem.get_problem(pid=pid)
        for pid in set(api.problem.get_unlocked_pids(team["tid"])) -
        set(api.problem.get_solved_pids(team["tid"]))
    ]
    problem = random.choice(unlocked)
    iid = api.user.get_team(uid=user["uid"])["instances"][problem["pid"]]
    instance = api.problem.get_problem_instance(problem["pid"], team["tid"])
    api.problem.submit_key(
        team["tid"], problem["pid"], instance["flag"], uid=user["uid"])
