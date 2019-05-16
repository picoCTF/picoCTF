"""
Team Testing Module
"""

import api.common
import api.team
import api.user
import bcrypt
import pytest
from api.common import InternalException, WebException
from .common import (base_team, base_user, clear_collections,
                    ensure_empty_collections)
from .conftest import setup_db, teardown_db

dict_filter = lambda dict, items: {k: v for k, v in dict.items() if k in items}


class TestNewStyleTeams(object):

    @ensure_empty_collections("users", "teams")
    @clear_collections("users", "teams")
    def test_user_team_registration(self):
        """
        Tests the newer and simplified user creation.
        """
        user = dict_filter(base_user.copy(), [
            "username", "firstname", "lastname", "email", "eligibility",
            "affiliation"
        ])
        user["password"] = "test"
        uid = api.user.create_simple_user_request(user)

        team_data = {"team_name": "lolhax", "team_password": "s3cret"}
        api.team.create_new_team_request(team_data, uid=uid)

        team = api.user.get_team(uid=uid)

        assert team["team_name"] == team_data[
            "team_name"], "User does not belong to the new team."
        assert api.team.get_team(name=user["username"])["size"] == 0 and api.team.get_team(name=team_data["team_name"])["size"] == 1, \
            "Size calculations are incorrect for new registered team."


class TestTeams(object):
    """
    API Tests for team.py
    """

    def setup_class(self):
        setup_db()
        api.config.get_settings()
        api.config.change_settings({"max_team_size": 5})

    def teardown_class(self):
        teardown_db()

    @ensure_empty_collections("teams")
    @clear_collections("teams")
    def test_create_batch_teams(self, teams=10):
        """
        Tests team creation.

        Covers:
            team.create_team
            team.get_team
            team.get_all_teams
        """
        tids = []
        for i in range(teams):
            team = base_team.copy()
            team["team_name"] += str(i)
            tids.append(api.team.create_team(team))

        assert len(set(tids)) == len(tids), "tids are not unique."

        assert len(api.team.get_all_teams()) == len(
            tids), "Not all teams were created."

        for i, tid in enumerate(tids):
            name = base_team['team_name'] + str(i)

            team_from_tid = api.team.get_team(tid=tid)
            team_from_name = api.team.get_team(name=name)

            assert team_from_tid == team_from_name, "Team lookup from tid and name are not the same."

    @ensure_empty_collections("teams", "users")
    @clear_collections("teams", "users")
    def test_get_team_uids(self):
        """
        Tests the code that retrieves the list of uids on a team

        Covers:
            team.create_team
            user.create_simple_user_request
            team.get_team_uids
        """

        team = base_team.copy()
        tid = api.team.create_team(team)

        uids = []
        for i in range(api.config.get_settings()["max_team_size"]):
            test_user = base_user.copy()
            test_user['username'] += str(i)
            uid = api.user.create_simple_user_request(test_user)
            uids.append(uid)

            # join a real team
            api.team.join_team(team["team_name"], team["password"], uid)

        team_uids = api.team.get_team_uids(tid)
        assert len(team_uids) == api.config.get_settings()[
            "max_team_size"], "Team does not have correct number of members"
        assert sorted(uids) == sorted(
            team_uids), "Team does not have the correct members"

    @ensure_empty_collections("teams", "users")
    @clear_collections("teams", "users")
    def test_create_user_request_team_size_validation(self):
        """
        Tests the team size restriction

        Covers:
            team.create_team
            user.create_user_request
        """

        team = base_team.copy()
        tid = api.team.create_team(team)

        uid = None
        for i in range(api.config.get_settings()["max_team_size"]):
            test_user = base_user.copy()
            test_user['username'] += str(i)
            uid = api.user.create_simple_user_request(test_user)
            # join a real team
            api.team.join_team(team["team_name"], team["password"], uid)

        with pytest.raises(InternalException):
            uid_fail = api.user.create_simple_user_request(base_user.copy())
            # join a real team
            api.team.join_team(team["team_name"], team["password"], uid_fail)
            assert False, "Team has too many users"

        api.user.disable_account(uid)

        # Should be able to add another user after disabling one.
        test_user = base_user.copy()
        test_user['username'] += "addition"
        uid = api.user.create_simple_user_request(test_user)
        api.team.join_team(team["team_name"], team["password"], uid)
