"""Tests for the /api/v1/teams routes."""
from pytest_mongo import factories
from ..common import ( # noqa (fixture)
  ADMIN_DEMOGRAPHICS,
  clear_db,
  client,
  decode_response,
  get_csrf_token,
  register_test_accounts,
  TEACHER_DEMOGRAPHICS,
  STUDENT_DEMOGRAPHICS,
  get_conn
)


def test_create_team(mongo_proc, client): # noqa (fixture)
    """Tests the POST /teams endpoint."""
    clear_db()
    register_test_accounts()

    # Attempt to create a new team as a teacher
    client.post('/api/v1/user/login', json={
        'username': TEACHER_DEMOGRAPHICS['username'],
        'password': TEACHER_DEMOGRAPHICS['password']
    })

    res = client.post('/api/v1/teams', json={
        'team_name': 'newteam',
        'team_password': 'newteam'
    })
    assert res.status_code == 403
    assert res.json['message'] == 'Teachers may not create teams'
    client.get('/api/v1/user/logout')

    # Attempt to create a team with a name previously used by a user
    client.post('/api/v1/user/login', json={
        'username': STUDENT_DEMOGRAPHICS['username'],
        'password': STUDENT_DEMOGRAPHICS['password']
    })
    res = client.post('/api/v1/teams', json={
        'team_name': ADMIN_DEMOGRAPHICS['username'],
        'team_password': 'newteam'
    })
    assert res.status_code == 409
    assert res.json['message'] == 'There is already a user with this name.'

    # Add a mock team and attempt to create a team with the same name
    db = get_conn()
    db.teams.insert({
        'team_name': 'test teamname'
    })
    res = client.post('/api/v1/teams', json={
        'team_name': 'test teamname',
        'team_password': 'newteam'
    })
    assert res.status_code == 409
    assert res.json['message'] == 'There is already a team with this name.'

    # Create and join a team
    res = client.post('/api/v1/teams', json={
        'team_name': 'newteam',
        'team_password': 'newteam'
    })
    assert res.status_code == 201
    assert res.json['success'] is True
    new_tid = res.json['tid']

    # Check that membership has been transferred
    user = db.users.find_one({'username': STUDENT_DEMOGRAPHICS['username']})
    old_team = db.teams.find_one({'team_name': STUDENT_DEMOGRAPHICS['username']})
    new_team = db.teams.find_one({'tid': new_tid})
    assert user['tid'] == new_tid
    assert old_team['size'] == 0
    assert new_team['size'] == 1

    # Attempt to create another team as the same user
    res = client.post('/api/v1/teams', json={
        'team_name': 'newteam2',
        'team_password': 'newteam2'
    })
    assert res.status_code == 422
    assert res.json['message'] == "You can only create one new team per " + \
                                  "user account!"
