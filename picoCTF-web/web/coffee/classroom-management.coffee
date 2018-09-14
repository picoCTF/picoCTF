Input = ReactBootstrap.Input
Row = ReactBootstrap.Row
Col = ReactBootstrap.Col
Button = ReactBootstrap.Button
ButtonGroup = ReactBootstrap.ButtonGroup
Panel = ReactBootstrap.Panel
ListGroup = ReactBootstrap.ListGroup
ListGroupItem = ReactBootstrap.ListGroupItem
Glyphicon = ReactBootstrap.Glyphicon
TabbedArea = ReactBootstrap.TabbedArea
TabPane = ReactBootstrap.TabPane

update = React.addons.update

MemberManagementItem = React.createClass
  removeTeam: ->
    apiCall "POST", "/api/group/teacher/leave", {gid: @props.gid, tid: @props.tid}
    .done ((resp) ->
      apiNotify resp
      @props.refresh()
    ).bind this

  switchUserRole: (tid, role) ->
    apiCall "POST", "/api/group/teacher/role_switch", {gid: @props.gid, tid: tid, role: role}
    .done ((resp) ->
      apiNotify resp
      @props.refresh()
    ).bind this

  render: ->
    if @props.teacher
      userButton =
      <Button bsStyle="success" className="btn-sq">
        <Glyphicon glyph="user" bsSize="large"/>
        <p className="text-center">Teacher</p>
      </Button>
    else
      userButton =
      <Button bsStyle="primary" className="btn-sq">
        <Glyphicon glyph="user" bsSize="large"/>
        <p className="text-center">User</p>
      </Button>

    if @props.teacher
      switchUser = <Button onClick={@switchUserRole.bind(null, @props.tid, "member")}>Make Member</Button>
    else
      switchUser = <Button onClick={@switchUserRole.bind(null, @props.tid, "teacher")}>Make Teacher</Button>

    <ListGroupItem>
      <Row className="row">
        <Col xs={2}>
          {userButton}
        </Col>
        <Col xs={6}>
          <h4>{@props.team_name}</h4>
          <p><strong>Affiliation:</strong> {@props.affiliation}</p>
        </Col>
        <Col xs={4}>
          <ButtonGroup vertical>
            {switchUser}
            <Button onClick={@removeTeam}>Remove User</Button>
          </ButtonGroup>
        </Col>
      </Row>
    </ListGroupItem>

MemberInvitePanel = React.createClass
  mixins: [React.addons.LinkedStateMixin]

  propTypes:
    gid: React.PropTypes.string.isRequired

  getInitialState: ->
    role: "member"

  inviteUser: (e) ->
    e.preventDefault()
    apiCall "POST", "/api/group/invite", {gid: @props.gid, email: @state.email, role: @state.role}
    .done ((resp) ->
      apiNotify resp
      @setState update @state, $set: email: ""
      @props.refresh()
    ).bind this

  render: ->
    <Panel>
      <form onSubmit={@inviteUser}>
        <Col xs={8}>
          <Input type="email" label="E-mail" valueLink={@linkState "email"}/>
        </Col>
        <Col xs={4}>
          <Input type="select" label="Role" placeholder="Member" valueLink={@linkState "role"}>
            <option value="member">Member</option>
            <option value="teacher">Teacher</option>
          </Input>
        </Col>
        <Col xs={4}>
          <Button onClick={@inviteUser}>Invite User</Button>
        </Col>
      </form>
    </Panel>

MemberManagement = React.createClass
  render: ->
    allMembers = update @props.teacherInformation, {$push: @props.memberInformation}
    allMembers = _.filter allMembers, ((member) -> @props.currentUser["tid"] != member["tid"]).bind this

    memberInformation = <ListGroup>
        {allMembers.map ((member, i) ->
          <MemberManagementItem key={i} gid={@props.gid} refresh={@props.refresh} {...member}/>
        ).bind this}
      </ListGroup>

    <Panel>
      <h4>User Management</h4>
      {memberInformation}
    </Panel>

GroupManagement = React.createClass
  getInitialState: ->
    name: ""
    settings:
      email_filter: []
      hidden: false
    member_information: []
    teacher_information: []
    current_user: {}

  componentWillMount: ->
    @refreshSettings()

  refreshSettings: ->
    apiCall "GET", "/api/group/settings", {gid: @props.gid}
    .done ((resp) ->
      @setState update @state, $merge: resp.data
    ).bind this

    apiCall "GET", "/api/user/status"
    .done ((resp) ->
      @setState update @state, current_user: $set: resp.data
      if not resp.data["teacher"] or (window.userStatus and not window.userStatus.teacher)
        apiNotify {status: 1, message: "You are no longer a teacher."}, "/profile"
    ).bind this

    apiCall "GET", "/api/group/member_information", {gid: @props.gid}
    .done ((resp) ->
      @setState update @state, member_information: $set: resp.data
    ).bind this

    apiCall "GET", "/api/group/teacher_information", {gid: @props.gid}
    .done ((resp) ->
      @setState update @state, teacher_information: $set: resp.data
    ).bind this

  pushUpdates: (modifier) ->
    data = @state

    if modifier
      data.settings = modifier data.settings

    apiCall "POST", "/api/group/settings", {gid: @props.gid, settings: JSON.stringify data.settings}
    .done ((resp) ->
      apiNotify resp
      @refreshSettings()
    ).bind this

  render: ->
    <div className="row" style={ "margin-top": "10px"}>
      <Col sm={6}>
        <MemberManagement teacherInformation={@state.teacher_information} currentUser={@state.current_user}
          memberInformation={@state.member_information} gid={@props.gid} refresh={@refreshSettings}/>
      </Col>
      <Col sm={6}>
        <GroupOptions pushUpdates={@pushUpdates} settings={@state.settings} gid={@props.gid}/>
      </Col>
    </div>

GroupOptions = React.createClass
  propTypes:
    settings: React.PropTypes.object.isRequired
    pushUpdates: React.PropTypes.func.isRequired
    gid: React.PropTypes.string.isRequired

  promptGroupHide: ->
    window.confirmDialog "This option will hide all members of this classroom from public or competition scoreboards. This change is irrevocable; you will not be able to change this back later.", "Hidden Classroom Change",
    "Okay", "Cancel", (() ->
      @props.pushUpdates ((data) -> update data, {hidden: {$set: true}})
    ).bind this, () -> false

  render: ->
    if @props.settings.hidden
      hiddenGroupDisplay =
        <p>This classroom is <b>hidden</b> from the general scoreboard.</p>
    else
      hiddenGroupDisplay =
        <p>
          This classroom is <b>visible</b> on the scoreboard.
          Click <a href="#" onClick={@promptGroupHide}>here</a> to hide it.
        </p>

    <Panel>
      <h4>Classroom Options</h4>
      <Panel>
        <form>
          {hiddenGroupDisplay}
        </form>
      </Panel>
    </Panel>

EmailWhitelistItem = React.createClass
  propTypes:
    email: React.PropTypes.string.isRequired
    pushUpdates: React.PropTypes.func.isRequired

  render: ->
    removeEmail = @props.pushUpdates.bind null, ((data) ->
      update data, {email_filter: {$apply: _.partial _.without, _, @props.email}}
    ).bind this

    <ListGroupItem>
      *@{@props.email}
      <span className="pull-right"><Glyphicon glyph="remove" onClick={removeEmail}/></span>
    </ListGroupItem>

GroupEmailWhitelist = React.createClass
  mixins: [React.addons.LinkedStateMixin]

  getInitialState: -> {}

  propTypes:
    pushUpdates: React.PropTypes.func.isRequired
    emails: React.PropTypes.array.isRequired
    gid: React.PropTypes.string.isRequired

  addEmailDomain: (e) ->
    # It would probably make more sense to this kind of validation server side.
    # However, it can't cause any real issue being here.

    e.preventDefault()

    if _.indexOf(@props.emails, @state.emailDomain) != -1
      apiNotify {status: 0, message: "This email domain has already been whitelisted."}
    else if _.indexOf(@state.emailDomain, "@") != -1
      apiNotify {status: 0, message: "You should not include '@'. I want the email domain that follows '@'."}
    else if _.indexOf(@state.emailDomain, ".") == -1
        apiNotify {status: 0, message: "Your email domain did not include a '.' as I expected. Please make sure this is an email domain."}
    else
      @props.pushUpdates ((data) ->
        #Fine because @setState won't affect the next line
        @setState update @state, $set: emailDomain: ""
        update data, email_filter: $push: [@state.emailDomain]
      ).bind this

  createItemDisplay: ->
    <ListGroup>
      {@props.emails.map ((email, i) ->
        <EmailWhitelistItem key={i} email={email} pushUpdates={@props.pushUpdates}/>
      ).bind this}
    </ListGroup>

  render: ->
    emptyItemDisplay =
      <p>The whitelist is current empty. All emails will be accepted during registration.</p>

    <div>
      <h4>Email Domain Whitelist</h4>
        <Panel>
          <form onSubmit={@addEmailDomain}>
            <Input type="text" addonBefore="@ Domain" valueLink={@linkState "emailDomain"}/>
            {if @props.emails.length > 0 then @createItemDisplay() else emptyItemDisplay}
          </form>
        </Panel>
    </div>

TeacherManagement = React.createClass
  getInitialState: ->
    groups: []
    tabKey: 0

  onTabSelect: (tab) ->
    @setState update @state, tabKey: $set: tab

  componentWillMount: ->
    apiCall "GET", "/api/group/list"
    .done ((resp) ->
      @setState update @state, groups: $set: resp.data
    ).bind this

  render: ->
    <TabbedArea activeKey={@state.tabKey} onSelect={@onTabSelect}>
      {@state.groups.map ((group, i) ->
        <TabPane eventKey={i} key={i} tab={group.name} className="tab-pane-outline">
          <GroupManagement key={group.name} gid={group.gid}/>
        </TabPane>
      ).bind this}
    </TabbedArea>
$ ->
  React.render <TeacherManagement/>, document.getElementById "group-management"

  $(document).on 'shown.bs.tab', 'a[href="#group-management-tab"]', () ->
    React.unmountComponentAtNode document.getElementById "group-management"
    React.render <TeacherManagement/>, document.getElementById "group-management"

