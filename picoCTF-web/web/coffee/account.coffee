updatePassword = (e) ->
  e.preventDefault()
  apiCall "POST", "/api/user/update_password", $("#password-update-form").serializeObject()
  .done (data) ->
    switch data['status']
      when 1
        ga('send', 'event', 'Authentication', 'UpdatePassword', 'Success')
      when 0
        ga('send', 'event', 'Authentication', 'UpdatePassword', 'Failure::' + data.message)
    apiNotify data, "/account"

resetPassword = (e) ->
  e.preventDefault()
  form = $("#password-reset-form").serializeObject()
  form["reset-token"] = window.location.hash.substring(1)
  apiCall "POST", "/api/user/confirm_password_reset", form
  .done (data) ->
    ga('send', 'event', 'Authentication', 'ResetPassword', 'Success')
    apiNotify data, "/"

disableAccount = (e) ->
  e.preventDefault()
  confirmDialog("This will disable your account, drop you from your team, and prevent you from playing!", "Disable Account Confirmation", "Disable Account", "Cancel",
  () ->
    form = $("#disable-account-form").serializeObject()
    apiCall "POST", "/api/user/disable_account", form
    .done (data) ->
      ga('send', 'event', 'Authentication', 'DisableAccount', 'Success')
      apiNotify data, "/")

Input = ReactBootstrap.Input
Row = ReactBootstrap.Row
Col = ReactBootstrap.Col
Button = ReactBootstrap.Button
Panel = ReactBootstrap.Panel
Glyphicon = ReactBootstrap.Glyphicon
ButtonInput = ReactBootstrap.ButtonInput
ButtonGroup = ReactBootstrap.ButtonGroup

update = React.addons.update

# Should figure out how we want to share components.
TeamManagementForm = React.createClass
  mixins: [React.addons.LinkedStateMixin]

  getInitialState: ->
    user: {}
    team: {}
    team_name: ""
    team_password: ""

  componentWillMount: ->
    apiCall "GET", "/api/user/status"
    .done ((api) ->
      @setState update @state,
        user: $set: api.data
    ).bind this

    apiCall "GET", "/api/team"
    .done ((api) ->
      @setState update @state,
        team: $set: api.data
    ).bind this

  onTeamRegistration: (e) ->
    e.preventDefault()
    if (!@state.team_name || !@state.team_password)
      apiNotify({status: 0, message: "Invalid team name or password."})
    else
      apiCall "POST", "/api/team/create", {team_name: @state.team_name, team_password: @state.team_password}
      .done (resp) ->
        switch resp.status
          when 0
              apiNotify resp
          when 1
              document.location.href = "/profile"

  onTeamJoin: (e) ->
    e.preventDefault()
    apiCall "POST", "/api/team/join", {team_name: @state.team_name, team_password: @state.team_password}
    .done (resp) ->
      switch resp.status
        when 0
            apiNotify resp
        when 1
            document.location.href = "/profile"


  onTeamPasswordChange: (e) ->
    e.preventDefault()
    if @state.team_password != @state.confirm_team_password
      apiNotify {status: 0, message: "Passwords do not match."}
    else
      newpass = @state.team_password
      newpass_confirm = @state.confirm_team_password
      confirmDialog("This will change the password needed to join your team.", "Team Password Change Confirmation", "Confirm", "Cancel",
      () ->
        apiCall "POST", "/api/team/update_password", {"new-password": newpass, "new-password-confirmation": newpass_confirm}
        .done (resp) ->
          switch resp.status
            when 0
                apiNotify resp
            when 1
                apiNotify resp, "/account"
      )

  listMembers: () ->
    for member in @state.team["members"]
      <li>{member.username}</li>


  render: ->
    if @state.team.max_team_size > 1 and not @state.user.teacher
      towerGlyph = <Glyphicon glyph="tower"/>
      lockGlyph = <Glyphicon glyph="lock"/>

      teamCreated = (@state.user and @state.user.username != @state.user.team_name)
      if teamCreated
        <Panel header="Team Management">
        <p><strong>Team Name:</strong> {@state.team.team_name}</p>
        <p><strong>Members</strong> ({@state.team.members.length}/{@state.team.max_team_size}):</p>
        <ul>
          {@listMembers()}
        </ul>

        <hr/>
          <form onSubmit={@onTeamPasswordChange}>
            <Input type="password" valueLink={@linkState "team_password"} addonBefore={lockGlyph} label="New Team Password" required/>
            <Input type="password" valueLink={@linkState "confirm_team_password"} addonBefore={lockGlyph} label="Confirm New Team Password" required/>
            <Col md={6}>
                <Button type="submit">Change Team Password</Button>
            </Col>
          </form>
        </Panel>
      else
        <Panel header="Team Management">
        <p>To avoid confusion on the scoreboard, you may not create a team that shares the same name as an existing user.</p>
          <form onSubmit={@onTeamJoin}>
            <Input type="text" valueLink={@linkState "team_name"} addonBefore={towerGlyph} label="Team Name" required/>
            <Input type="password" valueLink={@linkState "team_password"} addonBefore={lockGlyph} label="Team Password" required/>
            <Col md={6}>
              <span>
                <Button type="submit">Join Team</Button>
                <Button onClick={@onTeamRegistration}>Register Team</Button>
              </span>
            </Col>
          </form>
        </Panel>
    else
      <div/>

$ ->
  $("#password-update-form").on "submit", updatePassword
  $("#password-reset-form").on "submit", resetPassword
  $("#disable-account-form").on "submit", disableAccount

  React.render <TeamManagementForm/>, document.getElementById("team-management")
