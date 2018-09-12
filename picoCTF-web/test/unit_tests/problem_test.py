"""
Problem Testing Module
"""

import re

import api
import pytest
from api.common import APIException
from common import (clear_cache, clear_collections, ensure_empty_collections,
                    new_team_user)
from conftest import setup_db, teardown_db


class TestProblems(object):
    """
    API Tests for problem.py
    """

    # test keys
    correct = "test"
    wrong = "wrong"
    fake_sid = "acdb6a09cd2bae5f1bf53ed186a17248"

    def generate_base_problems(correct):
        """A workaround for python3's list comprehension scoping"""
        # create 5 base problems
        base_problems = [{
            "name":
            "base-" + str(i),
            "sanitized_name":
            "base-" + str(i),
            "score":
            10,
            "author":
            "haxxor",
            "category":
            "Binary Exploitation",
            "description":
            "Base problem " + str(i),
            "hints": ["test", "test2"],
            "instances": [{
                "description": "Base problem " + str(i),
                "flag": correct,
                "iid": 0,
                "server": "hack.com",
                "instance_number": 0
            }]
        } for i in range(5)]

        return base_problems

    base_problems = generate_base_problems(correct)

    def generate_disabled_problems(correct):
        """A workaround for python3's list comprehension scoping"""
        # create 5 disabled problems
        disabled_problems = [{
            "name":
            "locked-" + str(i),
            "sanitized_name":
            "locked-" + str(i),
            "author":
            "haxxor",
            "score":
            10,
            "category":
            "Reverse Engineering",
            "description":
            "Test",
            "hints": ["test", "test2"],
            "instances": [{
                "description": "disabled problem " + str(i),
                "flag": correct,
                "iid": 0,
                "server": "hack.com",
                "instance_number": 0
            }]
        } for i in range(5)]
        return disabled_problems

    disabled_problems = generate_disabled_problems(correct)

    def generate_problems(correct, base_problems):
        """A workaround for python3's list comprehension scoping"""

        # create 5 level1 problems
        level1_problems = [{
            "name":
            "level1-" + str(i),
            "sanitized_name":
            "level1-" + str(i),
            "score":
            60,
            "author":
            "haxxor",
            "category":
            "Forensics",
            "hints": ["test", "test"],
            "description":
            "Level1 problem " + str(i),
            "instances": [{
                "description": "Level1 problem " + str(i),
                "flag": correct,
                "iid": 0,
                "server": "hack.com",
                "instance_number": 0
            }]
        } for i in range(5)]

        return level1_problems

    level1_problems = generate_problems(correct, base_problems)

    def generate_bundle(base_problems, level1_problems):
        bundle = {
            "name":
            "test bundle",
            "author":
            "hacker joe",
            "categories": ["Test Problems"],
            "problems":
            [p["sanitized_name"] for p in base_problems + level1_problems],
            "description":
            "this is a test bundle",
        }

        dependencies = {}
        for p in level1_problems:
            dependency = {}
            dependency["weightmap"] = {
                dst["sanitized_name"]: 1 for dst in base_problems
            }
            dependency["threshold"] = len(base_problems)
            dependencies[p["sanitized_name"]] = dependency

        bundle["dependencies"] = dependencies
        return bundle

    bundle = generate_bundle(base_problems, level1_problems)

    enabled_problems = base_problems + level1_problems
    all_problems = enabled_problems + disabled_problems

    def setup_class(self):
        """
        Class setup code
        """

        setup_db()

        # initialization code
        self.uid = api.user.create_simple_user_request(new_team_user)
        self.tid = api.user.get_team(uid=self.uid)['tid']

        # insert all problems
        self.base_pids = []
        for problem in self.base_problems:
            pid = api.problem.insert_problem(problem, self.fake_sid)
            api.problem.update_problem(pid, {"disabled": False})
            self.base_pids.append(pid)

        self.enabled_pids = self.base_pids[:]
        for problem in self.level1_problems:
            pid = api.problem.insert_problem(problem, self.fake_sid)
            api.problem.update_problem(pid, {"disabled": False})
            self.enabled_pids.append(pid)

        self.disabled_pids = []
        for problem in self.disabled_problems:
            pid = api.problem.insert_problem(problem, self.fake_sid)
            self.disabled_pids.append(pid)

        self.all_pids = self.enabled_pids + self.disabled_pids

        # set the key as though they were generated properly
        # TODO: actually run generation
        for problem in api.problem.get_all_problems():
            api.problem.update_problem(problem["pid"], {"key": self.correct})

        # insert bundle and enable dependencies
        api.problem.insert_bundle(self.bundle)
        api.problem.set_bundle_dependencies_enabled(self.bundle["bid"], True)

    def teardown_class(self):
        teardown_db()

    def test_insert_problems(self):
        """
        Tests problem insertion.

        Covers:
            problem.insert_problem
            problem.get_problem
            problem.get_all_problems
        """

        # problems were inserted in initialization - try to insert the problems again
        for problem in self.all_problems:
            with pytest.raises(APIException):
                api.problem.insert_problem(problem, self.fake_sid)
                api.problem.update_problem(problem["pid"], {"disabled": False})
                assert False, "Was able to insert a problem twice."

        # verify that the enabled problems match
        db_problems = api.problem.get_all_problems()
        for problem in db_problems:
            assert problem['pid'] in self.enabled_pids, "Problems do not match"
            assert problem[
                'pid'] not in self.disabled_pids, "Problem should not be enabled"

        # verify that the disabled problems match
        db_all_problems = api.problem.get_all_problems(show_disabled=True)
        for problem in db_problems:
            assert problem['pid'] in self.all_pids

    @ensure_empty_collections("submissions")
    @clear_collections("submissions")
    @clear_cache()
    def test_submissions(self):
        """
        Tests key submissions.

        Covers:
            problem.submit_key
            problem.get_submissions
            problem.get_team_submissions
        """

        # test correct submissions
        for problem in self.base_problems[:2]:
            result = api.problem.submit_key(
                self.tid, problem['pid'], self.correct, uid=self.uid)
            assert result['correct'], "Correct key was not accepted"
            assert result['points'] == problem[
                'score'], "Did not return correct score"

            solved = api.problem.get_solved_pids(self.tid)
            assert problem['pid'] in solved

        # test incorrect submissions
        for problem in self.base_problems[2:]:
            result = api.problem.submit_key(
                self.tid, problem['pid'], self.wrong + "asd", uid=self.uid)
            assert not result['correct'], "Incorrect key was accepted"
            assert result['points'] == problem[
                'score'], "Did not return correct score"

            solved = api.problem.get_solved_problems(self.tid)
            assert api.problem.get_problem(pid=problem['pid']) not in solved

        # test submitting correct twice
        with pytest.raises(APIException):
            api.problem.submit_key(
                self.tid,
                self.base_problems[0]['pid'],
                self.correct,
                uid=self.uid)
            assert False, "Submitted key to problem that was already solved"

        # test submitting to disabled problem
        with pytest.raises(APIException):
            api.problem.submit_key(
                self.tid,
                self.disabled_problems[0]['pid'],
                self.correct,
                uid=self.uid)
            assert False, "Submitted key to disabled problem"

        # test getting submissions two ways
        assert len(api.problem.get_submissions(uid=self.uid)) == len(
            self.base_problems)
        assert len(api.problem.get_submissions(tid=self.tid)) == len(
            self.base_problems)

    @ensure_empty_collections("submissions")
    @clear_collections("submissions")
    @clear_cache()
    def test_get_unlocked_problems(self):
        """
        Tests getting the unlocked problems

        Covers:
            problem.get_unlocked_problems
            problem.submit_key
        """

        # check that base problems are unlocked
        unlocked = api.problem.get_unlocked_problems(self.tid)
        unlocked_pids = [p['pid'] for p in unlocked]
        for pid in self.base_pids:
            assert pid in unlocked_pids, "Base problem didn't unlock"

        # unlock more problems
        for problem in self.base_problems:
            api.problem.submit_key(
                self.tid, problem['pid'], self.correct, uid=self.uid)

        unlocked_pids = api.problem.get_unlocked_pids(self.tid)

        for pid in unlocked_pids:
            assert pid not in self.disabled_pids, "Disabled problem is unlocked"

        for pid in self.enabled_pids:
            assert pid in unlocked_pids, "Level1 problem didn't unlock"

    @ensure_empty_collections("submissions")
    @clear_collections("submissions", "problems")
    @clear_cache()
    def test_scoring(self):
        correct_total = 0
        for i, pid in enumerate(self.enabled_pids):
            problem = api.problem.get_problem(pid=pid)
            score = api.problem.submit_key(
                self.tid, problem['pid'], self.correct, uid=self.uid)['points']
            correct_total += problem['score']
            assert score == problem['score'], "submit_key return wrong score"
            team_total = api.stats.get_score(tid=self.tid)
            user_total = api.stats.get_score(uid=self.uid)
            solved_problems = api.problem.get_solved_pids(tid=self.tid)

            assert len(solved_problems
                      ) == i + 1, "The team has solved too many problems."
            assert api.stats.get_score(
                tid=self.
                tid) == correct_total, "Team score is calculating incorrectly!"
            assert api.stats.get_score(
                uid=self.
                uid) == correct_total, "User score is calculating incorrectly!"
