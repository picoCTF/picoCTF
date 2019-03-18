#!/usr/bin/env python3

from datetime import datetime
import api


def cache(f, *args, **kwargs):
    result = f(cache=False, *args, **kwargs)
    key = api.cache.get_mongo_key(f, *args, **kwargs)
    api.cache.set(key, result)
    return result


def run():
    print("Caching registration stats.")
    cache(api.stats.get_registration_count)

    print("Caching the public scoreboard entries...")
    cache(api.stats.get_all_team_scores, eligible=True, country=None, show_ineligible=False)
    cache(api.stats.get_all_team_scores, eligible=True, country=None, show_ineligible=True)

    print("Caching the public scoreboard graph...")
    cache(api.stats.get_top_teams_score_progressions, eligible=True, country=None, show_ineligible=False)
    cache(api.stats.get_top_teams_score_progressions, eligible=True, country=None, show_ineligible=True)

    print("Caching the scoreboard graph for each group...")
    for group in api.group.get_all_groups():
        cache(
            api.stats.get_top_teams_score_progressions,
            gid=group['gid'],
            show_ineligible=True)
        cache(api.stats.get_group_scores, gid=group['gid'])

    print("Caching number of solves for each problem.")
    for problem in api.problem.get_all_problems():
        print(problem["name"],
              cache(api.stats.get_problem_solves, pid=problem["pid"]))
