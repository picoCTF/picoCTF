"""
Imports and setup functionality
"""

import api.logger
import api.setup
import api.achievement
import api.user
import api.team
import api.group
import api.annotations
import api.auth
import api.common
import api.cache
import api.problem
import api.stats
import api.utilities
import api.problem_feedback
import api.admin
import api.shell_servers
import api.email
import api.token
import api.docker

# MUST BE LAST
import api.config

# Should not touch DB when just initializing the api
# this prevents programmatically importing the api
# api.setup.index_mongo()
