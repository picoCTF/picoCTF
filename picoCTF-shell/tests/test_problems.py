from os.path import dirname, join, realpath

import hacksport.deploy
from hacksport.deploy import deploy_problem
from shell_manager.util import default_config

PATH = dirname(realpath(__file__))

hacksport.deploy.deploy_config = default_config


class TestProblems:
    """
    Regression tests for compiled problems.
    """

    def test_compiled_sources(self):
        deploy_problem(join(PATH, "problems/compiled_sources"), test=True)

    def test_remote_compiled_makefile_template(self):
        deploy_problem(
            join(PATH, "problems/remote_compiled_makefile_template"), test=True)

    def test_remote_no_compile(self):
        deploy_problem(join(PATH, "problems/remote_no_compile"), test=True)

    def test_compiled_sources_url(self):
        deploy_problem(join(PATH, "problems/compiled_sources_url"), test=True)

    def test_high_level_compiled_binary(self):
        deploy_problem(join(PATH, "problems/local_compiled1"), test=True)
        deploy_problem(join(PATH, "problems/local_compiled2"), test=True)
        deploy_problem(join(PATH, "problems/remote_compiled1"), test=True)
