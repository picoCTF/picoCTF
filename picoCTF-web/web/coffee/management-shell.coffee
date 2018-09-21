Input = ReactBootstrap.Input
Button = ReactBootstrap.Button
ButtonToolbar = ReactBootstrap.ButtonToolbar
Grid = ReactBootstrap.Grid
Row = ReactBootstrap.Row
Col = ReactBootstrap.Col
Well = ReactBootstrap.Well
Accordion = ReactBootstrap.Accordion

ServerForm = React.createClass
  propTypes:
    new: React.PropTypes.bool.isRequired
    refresh: React.PropTypes.func.isRequired
    server: React.PropTypes.object

  getInitialState: ->
    if @props.new
      server = {
        "host": "", "port": 22, "username": "", "password": "",
        "protocol": "HTTP", "name": "", "server_number": 1
      }
    else
      server = @props.server

    {new: @props.new, shellServer: server}

  notifyAndRefresh: (data) ->
    apiNotify data
    @props.refresh()

  addServer: ->
    apiCall "POST", "/api/admin/shell_servers/add", @state.shellServer
    .done @notifyAndRefresh

  deleteServer: ->
    apiCall "POST", "/api/admin/shell_servers/remove", {"sid": @state.shellServer.sid}
    .done @notifyAndRefresh

  updateServer: ->
    apiCall "POST", "/api/admin/shell_servers/update", @state.shellServer
    .done @notifyAndRefresh

  loadProblems: ->
    apiCall "POST", "/api/admin/shell_servers/load_problems", {"sid": @state.shellServer.sid}
    .done @notifyAndRefresh

  checkStatus: ->
    apiCall "GET", "/api/admin/shell_servers/check_status", {"sid": @state.shellServer.sid}
    .done (data) ->
      apiNotify data

  updateHost: (e) ->
    copy = @state.shellServer
    copy.host = e.target.value
    @setState {shellServer: copy}

  updateName: (e) ->
    copy = @state.shellServer
    copy.name = e.target.value
    @setState {shellServer: copy}

  updatePort: (e) ->
    copy = @state.shellServer
    copy.port = parseInt(e.target.value)
    @setState {shellServer: copy}

  updateUsername: (e) ->
    copy = @state.shellServer
    copy.username = e.target.value
    @setState {shellServer: copy}

  updatePassword: (e) ->
    copy = @state.shellServer
    copy.password = e.target.value
    @setState {shellServer: copy}

  updateServerNumber: (e) ->
    copy = @state.shellServer
    copy.server_number = parseInt(e.target.value)
    @setState {shellServer: copy}

  updateProtocol: (value) ->
    copy = @state.shellServer
    copy.protocol = value
    @setState {shellServer: copy}

  render: ->
    nameDescription = "A unique name given to this shell server."
    hostDescription = "The host name of your shell server."
    portDescription = "The port that SSH is running on."
    usernameDescription = "The username to connect as - Be sure that this user has sudo privileges!"
    passwordDescription = "The password to use for authentication - Be sure that this is password is only used once."
    serverNumberDescription = "The designated server_number if sharding is enabled."
    protocolDescription = "The web protocol to access the problem files and shell server. This is most often just HTTP."

    if @state.new
      buttons =
        <ButtonToolbar className="pull-right">
          <Button onClick={@addServer}>Add</Button>
        </ButtonToolbar>
    else
      buttons =
        <ButtonToolbar className="pull-right">
          <Button onClick={@updateServer}>Update</Button>
          <Button onClick={@deleteServer}>Delete</Button>
          <Button onClick={@loadProblems}>Load Deployment</Button>
          <Button onClick={@checkStatus}>Check Status</Button>
        </ButtonToolbar>

    <div>
      {if @props.new then <TextEntry name="Name" type="text" value={@state.shellServer.name} onChange=@updateName description={nameDescription}/> else <span/>}
      <TextEntry name="Host" type="text" value={@state.shellServer.host} onChange=@updateHost description={hostDescription} />
      <TextEntry name="SSH Port" type="number" value={@state.shellServer.port.toString()} onChange=@updatePort description={portDescription} />
      <TextEntry name="Username" type="text" value={@state.shellServer.username} onChange=@updateUsername description={usernameDescription} />
      <TextEntry name="Password" type="password" value={@state.shellServer.password} onChange=@updatePassword description={passwordDescription} />
      <TextEntry name="Server Number" type="number" value={@state.shellServer.server_number.toString()} onChange=@updateServerNumber description={serverNumberDescription} />
      <OptionEntry name="Web Protocol" value={@state.shellServer.protocol} options={["HTTP", "HTTPS"]} onChange=@updateProtocol description={protocolDescription} />
      {buttons}
    </div>

ShellServerList = React.createClass

  getInitialState: ->
    {shellServers: []}

  refresh: ->
    apiCall "GET", "/api/admin/shell_servers"
    .done ((api) ->
      @setState {shellServers: api.data}
    ).bind this

  componentDidMount: ->
    @refresh()

  createShellServerForm: (server, i) ->
    if server == null
      shellServer = <ServerForm new={true} key={i+"new"} refresh={@refresh}/>
      header = <div> New Shell Server </div>
    else
      shellServer = <ServerForm new={false} server={server} key={server.sid} refresh={@refresh}/>
      header = <div>{server.name} - {server.host}</div>

    <Panel bsStyle={"default"} eventKey={i} key={i} header={header}>
      {shellServer}
    </Panel>

  render: ->
    serverList = _.map @state.shellServers, @createShellServerForm
    serverList.push(@createShellServerForm(null, @state.shellServers.length))

    <Accordion defaultActiveKey={0}>
      {serverList}
    </Accordion>

ProblemLoaderTab = React.createClass
  getInitialState: ->
    {publishedJSON: ""}

  handleChange: (e) ->
    @setState {publishedJSON: e.target.value}

  pushData: ->
    apiCall "POST", "/api/problems/load_problems", {competition_data: @state.publishedJSON}
    .done ((data) ->
      apiNotify data
      @clearPublishedJSON()
    ).bind this

  clearPublishedJSON: ->
    @setState {publishedJSON: ""}

  render: ->
    publishArea =
    <div className="form-group">
      <h4>
        <Hint text="This should be the output of running 'shell_manager publish' on your shell server."/>
        Paste your published JSON here:
      </h4>
      <Input className="form-control" type='textarea' rows="10"
        value={@state.publishedJSON} onChange={@handleChange}/>
    </div>

    <div>
      <Row>{publishArea}</Row>
      <Row>
        <ButtonToolbar>
          <Button onClick={@pushData}>Submit</Button>
          <Button onClick={@clearPublishedJSON}>Clear Data</Button>
        </ButtonToolbar>
      </Row>
    </div>


ShellServerTab = React.createClass

  render: ->
    <Well>
      <Grid>
        <Row>
          <h4>To add problems, enter your shell server information below.</h4>
        </Row>
        <Row>
          <Col md={6}>
            <ShellServerList />
          </Col>
        </Row>
      </Grid>
    </Well>
