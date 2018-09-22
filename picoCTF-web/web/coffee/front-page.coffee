Input = ReactBootstrap.Input
Row = ReactBootstrap.Row
Col = ReactBootstrap.Col
Button = ReactBootstrap.Button
Panel = ReactBootstrap.Panel
Glyphicon = ReactBootstrap.Glyphicon
ButtonInput = ReactBootstrap.ButtonInput
ButtonGroup = ReactBootstrap.ButtonGroup
Alert = ReactBootstrap.Alert

update = React.addons.update

LoginForm = React.createClass

  render: ->
    userGlyph = <Glyphicon glyph="user"/>
    lockGlyph = <Glyphicon glyph="lock"/>

    formButton = if @props.status == "Login" then \

    q = "'" #My syntax highlighting can't handle literal quotes in jsx. :(
    if @props.status == "Reset"
      <Panel>
        <form onSubmit={@props.onPasswordReset}>
          <p><i>A password reset link will be sent the user{q}s email.</i></p>
          <Input type="text" valueLink={@props.username} addonBefore={userGlyph} placeholder="Username" required="visible"/>
          <div style={{height: "70px"}}/>
          <Row>
            <Col md={6}>
              <ButtonInput type="submit">Reset Password</ButtonInput>
            </Col>
            <Col md={6}>
              <span className="pull-right pad">Go back to <a onClick={@props.setPage.bind null, "Login"}>Login</a>.</span>
            </Col>
          </Row>
        </form>
      </Panel>
    else
      showGroupMessage = (->
        <Alert bsStyle="info">
          You are registering as a member of <strong>{@props.groupName}</strong>.
        </Alert>
      ).bind this

      showEmailFilter = (->
        <Alert bsStyle="warning">
          You can register provided you have an email for one of these domains: <strong>{@props.emailFilter.join ", "}</strong>.
        </Alert>
      ).bind this

      registrationForm = if @props.status == "Register" then \
        <span>
          <Row>
            <div>
              {if @props.groupName.length > 0 then showGroupMessage() else <span/>}
              {if @props.emailFilter.length > 0 and not @props.rid then showEmailFilter() else <span/>}
            </div>
            <Col md={6}>
              <Input type="text" id="first-name" valueLink={@props.firstname} label="First Name" placeholder="Jane"/>
            </Col>
            <Col md={6}>
              <Input type="text" id="last-name" valueLink={@props.lastname} label="Last Name" placeholder="Doe"/>
            </Col>
          </Row>
          <Row>
            <Col md={12}>
              <Input type="email" id="email" valueLink={@props.email} label="E-mail" placeholder="email@example.com"/>
            </Col>
          </Row>
          <Row>
            <Col md={6}>
              <Input type="text" id="affiliation" valueLink={@props.affiliation} label="Affiliation" placeholder="Example School, Pittsburgh, PA"/>
            </Col>
            <Col md={6}>
              <Input type="select" label="Status" placeholder="Competitor" valueLink={@props.eligibility}>
                <option value="eligible">Competitor</option>
                <option value="ineligible">Instructor</option>
                <option value="ineligible">Other</option>
              </Input>
            </Col>
          </Row>
          <ButtonInput type="submit">Register</ButtonInput>
        </span> else <span/>

      <Panel>
        <form key={@props.status} onSubmit={if @props.status == "Login" then @props.onLogin else @props.onRegistration}>
          <Input type="text" id="username" valueLink={@props.username} addonBefore={userGlyph} label="Username"/>
          <Input type="password" id="password" valueLink={@props.password} addonBefore={lockGlyph} label="Password"/>
          <Row>
            <Col md={6}>
              {if @props.status == "Register" then \
                <span className="pad">Go back to <a onClick={@props.setPage.bind null, "Login"}>Login</a>.</span>
              else <span>
                <Button type="submit">Login</Button>
                <Button id="set-register" onClick={@props.setPage.bind null, "Register"}>Register</Button>
              </span>}
            </Col>
            <Col md={6}>
              <a className="pad" onClick={@props.setPage.bind null, "Reset"}>Need to reset your password?</a>
            </Col>
          </Row>
          {registrationForm}
        </form>
      </Panel>


TeamManagementForm = React.createClass
  mixins: [React.addons.LinkedStateMixin]

  getInitialState: ->
    team_name: ""
    team_password: ""

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

  render: ->

    towerGlyph = <Glyphicon glyph="tower"/>
    lockGlyph = <Glyphicon glyph="lock"/>

    <Panel>
      <p>To avoid confusion on the scoreboard, you may not create a team that shares the same name as an existing user.</p>
      <form onSubmit={@onTeamJoin}>
        <Input type="text" valueLink={@linkState "team_name"} addonBefore={towerGlyph} label="Team Name" required/>
        <Input type="password" valueLink={@linkState "team_password"} addonBefore={lockGlyph} label="Team Password" required/>
        <Col md={6}>
          <span> <Button type="submit">Join Team</Button>
            <Button onClick={@onTeamRegistration}>Register Team</Button>
          </span>
        </Col>
        <Col md={6}>
          <a href="#" onClick={() -> document.location.href = "/profile"}>Play as an individual.</a>
        </Col>
      </form>
    </Panel>

AuthPanel = React.createClass
  mixins: [React.addons.LinkedStateMixin]
  getInitialState: ->
    params = $.deparam $.param.fragment()

    page: "Login"
    settings: {}
    gid: params.g
    rid: params.r
    status: params.status
    groupName: ""
    eligibility: "eligible"
    regStats: {}

  componentWillMount: ->
    if @state.status == "verified"
      apiNotify({status: 1, message: "Your account has been successfully verified. Please login."})
    if @state.gid
      apiCall "GET", "/api/group/settings", {gid: @state.gid}
      .done ((resp) ->
        switch resp.status
          when 0
            apiNotify resp
          when 1
            @setState update @state,
              groupName: $set: resp.data.name
              affiliation: $set: resp.data.name
              settings: $merge: resp.data.settings
              page: $set: "Register"
      ).bind this
    else
      apiCall "GET", "/api/team/settings"
      .done ((resp) ->
        @setState update @state,
          settings: $merge: resp.data
      ).bind this

    apiCall "GET", "/api/user/status"
    .done ((resp) ->
      @setState update @state,
        settings: $merge: resp.data
     ).bind this

    apiCall "GET", "/api/stats/registration"
    .done ((resp) ->
      if resp.status
        @setState update @state,
          regStats: $set: resp.data
    ).bind this

  onRegistration: (e) ->
    e.preventDefault()

    apiCall "POST", "/api/user/create_simple", @state
    .done ((resp) ->
      switch resp.status
        when 0
          apiNotify resp
        when 1
          verificationAlert =
            status: 1
            message: "You have been sent a verification email. You will need to complete this step before logging in."

          if @state.settings.max_team_size > 1
            if @state.settings.email_verification and not @state.rid and @state.usertype != "teacher"
              apiNotify verificationAlert
              @setPage "Login"
              document.location.hash = "#team-builder"
            else
              apiNotify resp
              @setPage "Team Management"
          else
            if @state.settings.email_verification
              if not @state.rid or @state.rid.length == 0
                apiNotify verificationAlert
              else
                apiNotify resp, "/profile"
              @setPage "Login"
              if @state.settings.max_team_size > 1
                document.location.hash = "#team-builder"
            else
             apiNotify resp, "/profile"

    ).bind this

  onPasswordReset: (e) ->
    e.preventDefault()
    apiCall "POST", "/api/user/reset_password", {username: @state.username}
    .done ((resp) ->
      apiNotify resp
      if resp.status == 1
        @setPage "Login"
    ).bind this

  onLogin: (e) ->
    e.preventDefault()
    apiCall "POST", "/api/user/login", {username: @state.username, password: @state.password}
    .done ((resp) ->
      switch resp.status
        when 0
            apiNotify resp
        when 1
          if document.location.hash == "#team-builder" and not resp.data.teacher
            @setPage "Team Management"
          else
            if resp.data.teacher
              document.location.href = "/classroom"
            else
              document.location.href = "/profile"
    ).bind this

  setPage: (page) ->
    @setState update @state,
        page: $set: page

  componentDidMount: ->
    $("input").prop 'required', true

  componentDidUpdate: ->
    $("input").prop 'required', true

  render: ->
    links =
    username: @linkState "username"
    password: @linkState "password"
    lastname: @linkState "lastname"
    firstname: @linkState "firstname"
    email: @linkState "email"
    affiliation: @linkState "affiliation"
    eligibility: @linkState "eligibility"

    showRegStats = (()->
      if @state.regStats
        <Panel>
          <h4><strong>Registration Stats</strong></h4>
          <p><strong>{@state.regStats.users}</strong> users registered. <strong>{@state.regStats.teamed_users}</strong> users have
              joined <strong>{@state.regStats.teams}</strong> teams. <strong>{@state.regStats.groups}</strong> classrooms have been
              created.</p>
        </Panel>
    ).bind this

    if @state.page == "Team Management"
      <div>
        <Row>
          <Col md={6} mdOffset={3}>
            <TeamManagementForm/>
          </Col>
        </Row>
      </div>
    else
      <div>
        <Row>
            <Col md={6} mdOffset={3}>
              <LoginForm setPage={@setPage} status={@state.page} onRegistration={@onRegistration}
                onLogin={@onLogin} onPasswordReset={@onPasswordReset} emailFilter={@state.settings.email_filter}
                groupName={@state.groupName} rid={@state.rid} gid={@state.gid} {...links}/>
              {showRegStats()}
            </Col>
        </Row>
      </div>

$ ->
  redirectIfLoggedIn()
  React.render <AuthPanel/>, document.getElementById("auth-box")
