"""
Group Testing Module
"""

import api.common
import api.team
import api.user
import bcrypt
import pytest
from api.common import InternalException, WebException
from .common import clear_collections, ensure_empty_collections, new_team_user
from .conftest import setup_db, teardown_db


class TestGroups(object):
    """
    API Tests for group.py
    """

    base_teams = [{
        "team_name": "team" + str(i),
        "school": "Test HS",
        "password": "much_protected"
    } for i in range(5)]

    base_group = {
        "group-owner": new_team_user["username"],
        "group-name": "group_yo"
    }

    def setup_class(self):
        setup_db()

        # create teams
        self.tids = []
        for team in self.base_teams:
            self.tids.append(api.team.create_team(team))

        self.owner_uid = api.user.create_simple_user_request(new_team_user)
        api.admin.give_admin_role(new_team_user['username'])
        self.owner_tid = api.user.get_team(uid=self.owner_uid)['tid']

    def teardown_class(self):
        teardown_db()

    @ensure_empty_collections("groups")
    @clear_collections("groups")
    def test_create_batch_groups(self, groups=10):
        """
        Tests group creation and lookups

        Covers:
            group.create_group
            group.get_group

        """

        gids = []
        for i in range(groups):
            group = self.base_group.copy()
            group["group-name"] += str(i)

            gids.append(
                api.group.create_group(self.owner_tid, group["group-name"]))

        assert len(api.team.get_groups(uid=self.owner_uid, tid=self.owner_tid)) \
            == len(gids), "Not all groups were created."

        with pytest.raises(InternalException):
            api.group.get_group(gid="Not a real gid")
            assert False, "Looked up group with invalid gid!"

        with pytest.raises(InternalException):
            api.group.get_group(name="Not a real name")
            assert False, "Looked up group with invalid name!"

    @ensure_empty_collections("groups")
    @clear_collections("groups")
    def test_join_and_leave_group(self):
        """
        Tests leaving and joining groups

        Covers:
            group.create_group
            group.get_group
            group.join_group
            group.leave_group
        """

        group = self.base_group.copy()
        gid = api.group.create_group(self.owner_tid, group["group-name"])

        name = api.group.get_group(gid=gid)["name"]

        params = {"group-name": name, "group-owner": new_team_user["username"]}

        for tid in self.tids:
            if tid is not self.owner_tid:
                api.group.join_group(gid, tid)
                assert tid in api.group.get_group(gid=gid)['members']

        for tid in self.tids:
            api.group.leave_group(gid, tid)
            assert tid not in api.group.get_group(gid=gid)['members']

        with pytest.raises(InternalException):
            api.group.leave_group(gid, self.owner_tid)
            assert False, "Was able to leave group twice!"
