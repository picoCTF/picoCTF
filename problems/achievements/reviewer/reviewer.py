def process(api, data):
    return api.stats.get_team_review_count(tid=data["tid"]) >= 5, {}
