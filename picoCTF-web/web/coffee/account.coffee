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

    apiCall "GET", "/api/team/settings"
    .done ((api) ->
      @setState update @state,
        team: $set: api.data
    ).bind this

  onTeamRegistration: (e) ->
    e.preventDefault()
    if (!@state.team_name || !@state.team_password)
      apiNotify({status: 0, message: "Invalid Team name or password."})
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

  render: ->

    if @state.team.max_team_size > 1
      towerGlyph = <Glyphicon glyph="tower"/>
      lockGlyph = <Glyphicon glyph="lock"/>

      shouldDisable = if @state.user and @state.user.username != @state.user.team_name then "disabled" else ""

      <Panel header="Team Management">
        <form onSubmit={@onTeamJoin}>
          {if shouldDisable then <p>You can not switch or register your account to another team.</p> else <span/>}
          <Input type="text" valueLink={@linkState "team_name"} addonBefore={towerGlyph} label="Team Name" required disabled={shouldDisable}/>
          <Input type="password" valueLink={@linkState "team_password"} addonBefore={lockGlyph} label="Team Password" required disabled={shouldDisable}/>
          <Col md={6}>
            <span>
              <Button type="submit" disabled={shouldDisable}>Join Team</Button>
              <Button onClick={@onTeamRegistration} disabled={shouldDisable}>Register Team</Button>
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
