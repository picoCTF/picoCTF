#!/usr/bin/env python3


import api
import api.group
from api.stats import (check_invalid_instance_submissions, get_all_team_scores,
                       get_group_scores, get_problem_solves,
                       get_registration_count,
                       get_top_teams_score_progressions)
import socket

# How long after primary stat host falls off to allow another to take primary
COOLDOWN_TIME = 5 * 60


def run():
    """Run the stat caching daemon."""
    with api.create_app().app_context():
        def cache(f, *args, **kwargs):
            result = f(reset_cache=True, *args, **kwargs)
            return result

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        host = s.getsockname()[0]
        s.close()

        _cache = api.cache.get_cache()
        active_stat_host = _cache.get("active_stat_host")
        if active_stat_host is not None and host != active_stat_host:
            raise SystemExit
        else:
            _cache.set("active_stat_host", host, COOLDOWN_TIME)

        print("Caching registration stats...")
        cache(get_registration_count)

        print("Caching the scoreboards...")
        for scoreboard in api.scoreboards.get_all_scoreboards():
            get_all_team_scores(scoreboard_id=scoreboard['sid'])

        print("Caching the score progressions for each scoreboard...")
        for scoreboard in api.scoreboards.get_all_scoreboards():
            cache(get_top_teams_score_progressions,
                  limit=5,
                  scoreboard_id=scoreboard['sid'])

        print("Caching the scores and score progressions for each group...")
        for group in api.group.get_all_groups():
            get_group_scores(gid=group['gid'])
            cache(get_top_teams_score_progressions,
                  limit=5,
                  group_id=group['gid'])

        print("Caching number of solves for each problem...")
        for problem in api.problem.get_all_problems():
            print(problem["name"],
                  cache(get_problem_solves, problem["pid"]))

        print("Caching invalid instance submissions...")
        cache(check_invalid_instance_submissions)


if __name__ == '__main__':
    run()
