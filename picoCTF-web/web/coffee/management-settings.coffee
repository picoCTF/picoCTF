Well = ReactBootstrap.Well
ButtonGroup = ReactBootstrap.ButtonGroup
Button = ReactBootstrap.Button
Grid = ReactBootstrap.Grid
Row = ReactBootstrap.Row
Col = ReactBootstrap.Col

update = React.addons.update

# The settings fields need to use the linked state mixin to avoid a lot of boilerplate.

GeneralTab = React.createClass
  propTypes:
    refresh: React.PropTypes.func.isRequired
    settings: React.PropTypes.object.isRequired

  getInitialState: ->
    @props.settings

  toggleFeedbackEnabled: ->
    @setState update @state,
      $set:
        enable_feedback: !@state.enable_feedback

  updateCompetitionName: (e) ->
    @setState update @state,
      $set:
        competition_name: e.target.value

  updateCompetitionURL: (e) ->
    @setState update @state,
      $set:
        competition_url: e.target.value

  updateStartTime: (value) ->
    @setState update @state,
      $set:
        start_time:
          $date: value

  updateEndTime: (value) ->
    @setState update @state,
      $set:
        end_time:
          $date: value

  pushUpdates: ->
    apiCall "POST", "/api/admin/settings/change", {json: JSON.stringify(@state)}
    .done ((data) ->
      apiNotify data
      @props.refresh()
    ).bind(this)

  render: ->
    feedbackDescription = "Users will be able to review problems when this feature is enabled. The ratings will be available to you
      on the Problem tab."

    competitionNameDescription = "The name of the competition."
    competitionURLDescription = "The base URL for the competition website. This must be set in order for users to reset
      their passwords."

    startTimeDescription = "Before the competition has started, users will be able to register without viewing the problems."
    endTimeDescription = "After the competition has ended, users will no longer be able to submit keys to the challenges."

    <Well>
      <BooleanEntry name="Receive Problem Feedback" value={@state.enable_feedback} onChange=@toggleFeedbackEnabled description={feedbackDescription}/>
      <TextEntry name="Competition Name" value={@state.competition_name} type="text" onChange=@updateCompetitionName description={competitionNameDescription}/>
      <TextEntry name="Competition URL" value={@state.competition_url} type="text" onChange=@updateCompetitionURL description={competitionURLDescription}/>
      <TimeEntry name="Competition Start Time" value={@state.start_time["$date"]} onChange=@updateStartTime description={startTimeDescription}/>
      <TimeEntry name="Competition End Time" value={@state.end_time["$date"]} onChange=@updateEndTime description={endTimeDescription}/>

      <Row>
        <div className="text-center">
          <ButtonToolbar>
            <Button onClick={@pushUpdates}>Update</Button>
          </ButtonToolbar>
        </div>
      </Row>
    </Well>

EmailTab = React.createClass
  propTypes:
    refresh: React.PropTypes.func.isRequired
    emailSettings: React.PropTypes.object.isRequired
    loggingSettings: React.PropTypes.object.isRequired
    emailFilterSettings: React.PropTypes.array.isRequired

  getInitialState: ->
    settings = @props.emailSettings
    $.extend settings, @props.loggingSettings
    settings.email_filter = @props.emailFilterSettings
    settings

  updateSMTPUrl: (e) ->
    @setState update @state,
      $set:
        smtp_url: e.target.value

  updateSMTPSecurity: (e) ->
    @setState update @state,
      $set: smtp_security: e.target.value

  updateSMTPPort: (e) ->
    @setState update @state,
      $set:
        smtp_port: parseInt(e.target.value)

  updateUsername: (e) ->
    @setState update @state,
      $set:
        email_username: e.target.value

  updatePassword: (e) ->
    @setState update @state,
      $set:
        email_password: e.target.value

  updateFromAddr: (e) ->
    @setState update @state,
      $set:
        from_addr: e.target.value

  updateFromName: (e) ->
    @setState update @state,
      $set:
        from_name: e.target.value

  toggleEnabled: ->
    @setState update @state,
      $set:
        enable_email: !@state.enable_email

  toggleEmailVerification: ->
    @setState update @state,
      $set:
        email_verification: !@state.email_verification

  pushUpdates: (makeChange) ->
    pushData =
      email:
        enable_email: @state.enable_email
        email_verification: @state.email_verification
        smtp_url: @state.smtp_url
        smtp_port: @state.smtp_port
        email_username: @state.email_username
        email_password: @state.email_password
        from_addr: @state.from_addr
        from_name: @state.from_name
        smtp_security: @state.smtp_security
      logging:
        admin_emails: @state.admin_emails
      email_filter: @state.email_filter

    if typeof(makeChange) == "function"
      pushData = makeChange pushData

    apiCall "POST", "/api/admin/settings/change", {json: JSON.stringify(pushData)}
    .done ((data) ->
      apiNotify data
      @props.refresh()
    ).bind(this)

  render: ->
    emailDescription = "Emails must be sent in order for users to reset their passwords."
    emailVerificationDescription = "Mandate email verification for new users"
    SMTPDescription = "The URL of the STMP server you are using"
    SMTPPortDescription = "The port of the running SMTP server"
    usernameDescription = "The username of the email account"
    passwordDescription = "The password of the email account"
    fromAddressDescription = "The address that the emails should be sent from"
    fromNameDescription = "The name to use for sending emails"
    SMTPSecurityDescription = "Security employed by the SMTP server"

    # This is pretty bad. Much of this file needs reworked.
    if @state.smtp_security == "TLS"
        securityOptions =
        <Input type="select" onChange={@updateSMTPSecurity} key="TLS">
          <option value="TLS">TLS</option>
          <option value="SSL">SSL</option>
        </Input>
    else
        securityOptions =
        <Input type="select" onChange={@updateSMTPSecurity} key="SSL">
          <option value="SSL">SSL</option>
          <option value="TLS">TLS</option>
        </Input>

    SMTPSecuritySelect =
    <Row>
      <Col md={4}>
        <h4 className="pull-left">
          <Hint text={SMTPSecurityDescription}/>
          Security
        </h4>
      </Col>
      <Col md={8}>
        {securityOptions}
      </Col>
    </Row>

    <Well>
      <Row>
        <Col xs={6}>
          <BooleanEntry name="Send Emails" value={@state.enable_email} onChange=@toggleEnabled description={emailDescription}/>
          <TextEntry name="SMTP URL" value={@state.smtp_url} type="text" onChange=@updateSMTPUrl description={SMTPDescription} />
          <TextEntry name="SMTP Port" value={@state.smtp_port} type="number" onChange=@updateSMTPPort description={SMTPPortDescription} />
          <TextEntry name="Email Username" value={@state.email_username} type="text" onChange=@updateUsername description={usernameDescription}/>
          <TextEntry name="Email Password" value={@state.email_password} type="password" onChange=@updatePassword description={passwordDescription}/>
          <TextEntry name="From Address" value={@state.from_addr} type="text" onChange=@updateFromAddr description={fromAddressDescription}/>
          <TextEntry name="From Name" value={@state.from_name} type="text" onChange=@updateFromName description={fromNameDescription}/>
          <BooleanEntry name="Email Verification" value={@state.email_verification} onChange=@toggleEmailVerification description={emailVerificationDescription}/>
          {SMTPSecuritySelect}
          <Row>
            <div className="text-center">
              <ButtonToolbar>
                <Button onClick={@pushUpdates}>Update</Button>
              </ButtonToolbar>
            </div>
          </Row>
        </Col>
        <Col xs={6}>
          <EmailWhitelist pushUpdates={@pushUpdates} emails={@props.emailFilterSettings}/>
        </Col>
      </Row>
    </Well>

ShardingTab = React.createClass
  propTypes:
    refresh: React.PropTypes.func.isRequired
    shardingSettings: React.PropTypes.object.isRequired

  getInitialState: ->
    settings = @props.shardingSettings

  updateSteps: (e) ->
    @setState update @state,
      $set:
        steps: e.target.value.replace(/, +/g, ",").split(',').map(Number)

  updateDefaultStepping: (e) ->
    @setState update @state,
      $set:
        default_stepping: parseInt(e.target.value)

  toggleSharding: ->
    @setState update @state,
      $set:
        enable_sharding: !@state.enable_sharding

  toggleLimitRange: ->
    @setState update @state,
      $set:
        limit_added_range: !@state.limit_added_range

  pushUpdates: (makeChange) ->
    pushData =
      shell_servers:
        enable_sharding: @state.enable_sharding
        default_stepping: @state.default_stepping
        steps: @state.steps
        limit_added_range: @state.limit_added_range

    if typeof(makeChange) == "function"
      pushData = makeChange pushData

    apiCall "POST", "/api/admin/settings/change", {json: JSON.stringify(pushData)}
    .done ((data) ->
      apiNotify data
      @props.refresh()
    ).bind(this)

  render: ->
    shardingDescription = "Sharding splits teams to different shell_servers based on stepping"
    defaultSteppingDescription = "Default stepping, applied after defined steps"
    stepsDescription = "Comma delimited list of stepping (e.g. '1000,1500,2000')"
    limitRangeDescription = "Sharding splits teams to different shell_servers based on stepping"

    <Well>
      <Row>
        <Col sm={8}>
          <BooleanEntry name="Enable Sharding" value={@state.enable_sharding} onChange=@toggleSharding description={shardingDescription}/>
          <TextEntry name="Defined Steps" value={@state.steps} type="text" onChange=@updateSteps description={stepsDescription}/>
          <TextEntry name="Default Stepping" value={@state.default_stepping} type="text" onChange=@updateDefaultStepping description={defaultSteppingDescription}/>
          <BooleanEntry name="Limit to Added Range" value={@state.limit_added_range} onChange=@toggleLimitRange description={limitRangeDescription}/>
          <Row>
            <div className="text-center">
              <ButtonToolbar>
                <Button onClick={@pushUpdates}>Update</Button>
              </ButtonToolbar>
            </div>
          </Row>
        </Col>
      </Row>
    </Well>


SettingsTab = React.createClass
  getInitialState: ->
    settings:
      start_time:
        $date: 0
      end_time:
        $date: 0
      competition_name: ""
      competition_url: ""
      enable_feedback: true
      email:
        email_verification: false
        enable_email: false
        from_addr: ""
        smtp_url: ""
        smtp_port: 0
        email_username: ""
        email_password: ""
        from_name: ""
      logging:
        admin_emails: []
      email_filter: []
      shell_servers:
        enable_sharding: false
        default_stepping: 1
        steps: ""
        limit_added_range: false

    tabKey: "general"

  onTabSelect: (tab) ->
    @setState update @state,
      tabKey:
        $set: tab

  refresh: ->
    apiCall "GET", "/api/admin/settings"
    .done ((api) ->
      @setState update @state,
        $set:
          settings: api.data
    ).bind this

  componentDidMount: ->
    @refresh()

  render: ->
    generalSettings =
      enable_feedback: @state.settings.enable_feedback
      competition_name: @state.settings.competition_name
      competition_url: @state.settings.competition_url
      start_time: @state.settings.start_time
      end_time: @state.settings.end_time

    <Well>
      <Grid>
        <Row>
          <h4> Configure the competition settings by choosing a tab below </h4>
        </Row>
        <TabbedArea activeKey={@state.tabKey} onSelect={@onTabSelect}>
          <TabPane eventKey='general' tab='General'>
            <GeneralTab refresh=@refresh settings={generalSettings} key={Math.random()}/>
          </TabPane>

          <TabPane eventKey='sharding' tab='Sharding'>
            <ShardingTab refresh={@refresh} shardingSettings={@state.settings.shell_servers} key={Math.random()}/>
          </TabPane>

          <TabPane eventKey='email' tab='Email'>
            <EmailTab refresh={@refresh} emailSettings={@state.settings.email} emailFilterSettings={@state.settings.email_filter}
              loggingSettings={@state.settings.logging} key={Math.random()}/>
          </TabPane>
        </TabbedArea>
      </Grid>
    </Well>
