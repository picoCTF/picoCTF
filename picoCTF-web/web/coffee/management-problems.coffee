Panel = ReactBootstrap.Panel
Button = ReactBootstrap.Button
ButtonGroup = ReactBootstrap.ButtonGroup
Glyphicon = ReactBootstrap.Glyphicon
Col = ReactBootstrap.Col
Input = ReactBootstrap.Input
Label = ReactBootstrap.Label
PanelGroup = ReactBootstrap.PanelGroup
Row = ReactBootstrap.Row
ListGroup = ReactBootstrap.ListGroup
ListGroupItem = ReactBootstrap.ListGroupItem
CollapsibleMixin = ReactBootstrap.CollapsibleMixin
Table = ReactBootstrap.Table

update = React.addons.update

SortableButton = React.createClass
  propTypes:
    name: React.PropTypes.string.isRequired

  handleClick: (e) ->
    @props.onFocus @props.name

    if @props.active
      @props.onSortChange @props.name, !@props.ascending
    else
      #Make it active. No-op on sorting.
      @props.onSortChange @props.name, @props.ascending

  render: ->
    glyph = if @props.ascending then <Glyphicon glyph="chevron-down"/> else <Glyphicon glyph="chevron-up"/>
    <Button bsSize="small" active={@props.active} onClick={@handleClick}>{@props.name} {glyph}</Button>


SortableButtonGroup = React.createClass
  getInitialState: ->
    state = _.object ([name, {active: false, ascending: true}] for name in @props.data)
    state[@props.activeSort.name] = {active: true, ascending: @props.activeSort.ascending}
    state

  handleClick: (name) ->
    #Reset all active states.
    activeStates = _.reduce @getInitialState(), ((memo, sortState, name) ->
      memo[name] = {active: false, ascending: true}
      memo), {}
    activeStates[name].active = true
    @setState activeStates

  render: ->
    activeState = @state
    activeState[@props.activeSort.name] = {active: true, ascending: @props.activeSort.ascending}
    <ButtonGroup>
      {@props.data.map ((name, i) ->
        <SortableButton key={i} active={activeState[name].active} ascending={activeState[name].ascending}
          name={name} onSortChange={@props.onSortChange} onFocus={@handleClick}/>
      ).bind this}
    </ButtonGroup>

ProblemFilter = React.createClass
  propTypes:
    onFilterChange: React.PropTypes.func.isRequired
    filter: React.PropTypes.string

  getInitialState: ->
    filter: @props.filter

  onChange: ->
    filterValue = this.refs.filter.getInputDOMNode().value
    @setState {filter: filterValue}
    @props.onFilterChange filterValue

  render: ->
    glyph = <Glyphicon glyph="search"/>
    <Panel>
      <Col xs={12}>
        Search
        <Input type='text' className="form-control"
          ref="filter"
          addonBefore={glyph}
          onChange={@onChange}
          value={@state.filter}/>
      </Col>
      <Col xs={12}>
        <SortableButtonGroup key={@props.activeSort} activeSort={@props.activeSort}
          onSortChange={@props.onSortChange} data={["name", "category", "score"]}/>
      </Col>
    </Panel>

ProblemClassifierList = React.createClass
  render: ->
    categories = _.groupBy @props.problems, "category"
    categoryData = _.map categories, (problems, category) ->
      name: "Only #{category}"
      size: problems.length
      classifier: (problem) ->
        problem.category == category
    categoryData = _.sortBy categoryData, "name"

    organizations = _.groupBy @props.problems, "organization"
    organizationData = _.map organizations, (problems, organization) ->
      name: "Created by #{organization}"
      size: problems.length
      classifier: (problem) ->
        problem.organization == organization
    organizationData = _.sortBy organizationData, "name"

    problemStates = _.countBy @props.problems, "disabled"
    problemStateData = []

    if problemStates[false] > 0
      problemStateData.push
        name: "Enabled problems",
        size: problemStates[false],
        classifier: (problem) -> !problem.disabled

    if problemStates[true] > 0
      problemStateData.push
        name: "Disabled problems",
        size: problemStates[true],
        classifier: (problem) -> problem.disabled

    problemNames = _.map @props.problems, (problem) -> problem.sanitized_name
    bundleData = _.map @props.bundles, (bundle) ->
      name: bundle.name
      size: _.intersection(bundle.problems, problemNames).length
      classifier: (problem) -> problem.sanitized_name in bundle.problems

    <PanelGroup className="problem-classifier" collapsible>
      <ProblemClassifier name="State" data={problemStateData} {...@props}/>
      <ProblemClassifier name="Categories" data={categoryData} {...@props}/>
      <ProblemClassifier name="Organizations" data={organizationData} {...@props}/>
      <ProblemClassifier name="Bundles" data={bundleData} {...@props}/>
    </PanelGroup>

ClassifierItem = React.createClass
  handleClick: (e) ->
    @props.setClassifier !@props.active, @props.classifier, @props.name
    @props.onExclusiveClick @props.name

  render: ->
    glyph = <Glyphicon glyph="ok"/>

    <ListGroupItem onClick={@handleClick} className="classifier-item">
        {@props.name} {if @props.active then glyph} <div className="pull-right"><Badge>{@props.size}</Badge></div>
    </ListGroupItem>

ProblemClassifier = React.createClass
  getInitialState: ->
    _.object ([classifier.name, false] for classifier in @props.data)

  handleClick: (name) ->
    activeStates = @getInitialState()
    activeStates[name] = !@state[name]
    @setState activeStates

  render: ->
    <Panel header={@props.name} defaultExpanded collapsible>
      <ListGroup fill>
        {@props.data.map ((data, i) ->
          <ClassifierItem onExclusiveClick={@handleClick} active={@state[data.name]}
            key={i} setClassifier={@props.setClassifier} {...data}/>
        ).bind this}
      </ListGroup>
    </Panel>

CollapsibleInformation = React.createClass
  mixins: [CollapsibleMixin]

  classNames: (styles) ->
    _.reduce styles, ((memo, val, key) ->
      if val
        memo += " #{key}"
      memo), ""

  getCollapsibleDOMNode: ->
    React.findDOMNode @refs.panel

  getCollapsibleDimensionValue: ->
    (React.findDOMNode @refs.panel).scrollHeight;

  onHandleToggle: (e) ->
    e.preventDefault()
    @setState {expanded: !@state.expanded}

  render: ->
    styles = @getCollapsibleClassSet()
    glyph = if @state.expanded then "chevron-down" else "chevron-right"
    <div className="collapsible-information">
      <a onClick={this.onHandleToggle}>
        {@props.title} <Glyphicon glyph={glyph} className="collapsible-information-chevron"/>
      </a>
      <div ref="panel" className={@classNames styles}>
        {this.props.children}
      </div>
    </div>

ProblemFlagTable = React.createClass

  render: ->
    <Table responsive>
      <thead>
        <tr>
          <th>#</th>
          <th>Instance</th>
          <th>Flag</th>
        </tr>
      </thead>
      <tbody>
      {@props.instances.map (instance, i) ->
        <tr key={i}>
          <td>{i+1}</td>
          <td>{instance.iid}</td>
          <td>{instance.flag}</td>
        </tr>}
      </tbody>
    </Table>


ProblemHintTable = React.createClass
  render: ->
    <Table responsive>
      <thead>
        <tr>
          <th>#</th>
          <th>Hint</th>
        </tr>
      </thead>
      <tbody>
      {@props.hints.map (hint, i) ->
        <tr key={i}>
          <td>{i+1}</td>
          <td>{hint}</td>
        </tr>}
      </tbody>
    </Table>

ProblemReview = React.createClass
  render: ->
    upvotes = 0
    downvotes = 0
    for review in @props.reviews
      if review.feedback.liked
        upvotes++
      else
        downvotes++

    style = {
      fontSize:"2.0em"
    }

    <Row>
      <Col sm={6} md={6} lg={6}>
        <div className="pull-right">
          <Glyphicon glyph="thumbs-up" className="active pad" style={style}/>
          <Badge>{upvotes}</Badge>
        </div>
      </Col>
      <Col sm={6} md={6} lg={6}>
        <div className="pull-left">
          <Glyphicon glyph="thumbs-down" className="active pad" style={style}/>
          <Badge>{downvotes}</Badge>
        </div>
      </Col>
    </Row>

Problem = React.createClass

  getInitialState: ->
    expanded: false

  onStateToggle: (e) ->
    e.preventDefault()
    apiCall "POST", "/api/admin/problems/availability", {pid: @props.pid, state: !@props.disabled}
    .done @props.onProblemChange

  handleExpand: (e) ->
    e.preventDefault()

    #This is awkward.
    if $(e.target).parent().hasClass "do-expand"
      @setState {expanded: !@state.expanded}

  render: ->

    statusButton =
    <Button bsSize="xsmall" bsStyle={if @props.disabled then "default" else "default"} onClick={@onStateToggle}>
      {if @props.disabled then "Enable" else "Disable"} <Glyphicon glyph={if @props.disabled then "ok" else "minus"}/>
    </Button>

    problemHeader =
    <div>
      <span className="do-expand">{@props.category} - {@props.name}</span>
      <div className="pull-right">
        ({@props.score}) {statusButton}
      </div>
    </div>

    if @props.tags is undefined or @props.tags.length == 0
      problemFooter = "No tags"
    else
      problemFooter = @props.tags.map (tag, i) ->
        <Label key={i}>{tag}</Label>

    #Do something interesting here.
    panelStyle = if @props.disabled then "default" else "default"

    submissionDisplay = if @props.submissions and @props.submissions.valid + @props.submissions.invalid >= 1 then \
    <div>
      <h4 className="text-center"> Submissions </h4>
      <div style={{width: '200px', height: '200px', margin: 'auto'}}>
      <ProblemSubmissionDoughnut valid={@props.submissions.valid}
      invalid={@props.submissions.invalid} visible={@state.expanded} className="text-center"/>
      </div>
    </div>
    else <p>No solve attempts.</p>

    reviewDisplay =
      <ProblemReview reviews={@props.reviews} />

    if @state.expanded
      <Panel bsStyle={panelStyle} header={problemHeader} footer={problemFooter} collapsible
        expanded={@state.expanded} onSelect={@handleExpand}>
        <Row>
          <Col md={4}>
            {submissionDisplay}
            {reviewDisplay}
          </Col>
          <Col md={8}>
            <h4>
              {@props.author}
              {if @props.organization then " @ "+@props.organization}
            </h4>
            <hr/>
            <CollapsibleInformation title="Description">
              <p className="problem-description">{@props.description}</p>
            </CollapsibleInformation>
            <CollapsibleInformation title="Hints">
              <ProblemHintTable hints={@props.hints}/>
            </CollapsibleInformation>
            <CollapsibleInformation title="Instance Flags">
              <ProblemFlagTable instances={@props.instances}/>
            </CollapsibleInformation>
          </Col>
        </Row>
      </Panel>
    else
      <Panel bsStyle={panelStyle} header={problemHeader} footer={problemFooter} collapsible
        expanded={@state.expanded} onSelect={@handleExpand}/>

ProblemList = React.createClass
  propTypes:
    problems: React.PropTypes.array.isRequired

  render: ->
    if @props.problems.length == 0
      return <h4>No problems have been loaded. Click <a href='#'>here</a> to get started.</h4>

    problemComponents = @props.problems.map ((problem, i) ->
      <Col xs={12}>
        <Problem key={problem.name} onProblemChange={@props.onProblemChange} submissions={@props.submissions[problem.name]} {...problem}/>
      </Col>
    ).bind this

    <Row>
      {problemComponents}
    </Row>

ProblemDependencyView = React.createClass
  handleClick: (bundle) ->
    apiCall "POST", "/api/admin/bundle/dependencies_active", {bid: bundle.bid, state: !bundle.dependencies_enabled}
    .done @props.onProblemChange

  render: ->
    bundleDisplay = @props.bundles.map ((bundle, i) ->
      switchText = if bundle.dependencies_enabled then "Unlock Problems" else "Lock Problems"
      <ListGroupItem key={i} className="clearfix">
        <div>{bundle.name}
          <div className="pull-right">
            <Button bsSize="xsmall" onClick={@handleClick.bind null, bundle}>
              {switchText}
            </Button>
          </div>
        </div>
      </ListGroupItem>
    ).bind this

    <Panel header="Problem Dependencies">
      <p>
        { "By default, all problems are unlocked. You can enable or disable the problem unlock dependencies
        for your problem bundles below." }
      </p>
      <ListGroup fill>
        {bundleDisplay}
      </ListGroup>
    </Panel>

ProblemListModifiers = React.createClass

  onMassChange: (enabled) ->
    change = if enabled then "enable" else "disable"
    changeNumber = @props.problems.length
    window.confirmDialog "Are you sure you want to #{change} these #{changeNumber} problems?", "Mass Problem State Change",
    "Yes", "No", (() ->
      calls = _.map @props.problems, (problem) ->
        apiCall "POST", "/api/admin/problems/availability", {pid: problem.pid, state: !enabled}
      ($.when.apply this, calls)
        .done (() ->
          if _.all(_.map arguments, (call) -> (_.first call).status == 1)
            apiNotify {status: 1, message: "All problems have been successfully changed."}
          else
            apiNotify {status: 0, message: "There was an error changing some of the problems."}
          @props.onProblemChange()
        ).bind this
      ).bind this, () -> false

  render: ->
    <Panel>
      <ButtonGroup className="pull-right">
        <Button onClick={@onMassChange.bind null, true}>Enable All Problems</Button>
        <Button onClick={@onMassChange.bind null, false}>Disable All Problems</Button>
      </ButtonGroup>
    </Panel>


ProblemTab = React.createClass
  propTypes:
    problems: React.PropTypes.array.isRequired

  getInitialState: ->
    filterRegex: /.*/
    activeSort:
      name: "name"
      ascending: true
    problemClassifier: [
      {name: "all", func: (problem) -> true}
    ]

  onFilterChange: (filter) ->
    try
      newFilter = new RegExp filter, "i"
      @setState update @state,
        filterRegex: $set: newFilter
    catch
      # We shouldn't do anything.

  onSortChange: (name, ascending) ->
    @setState update @state,
      activeSort: $set: {name: name, ascending: ascending}

  setClassifier: (classifierState, classifier, name) ->
    if classifierState
      @setState update @state,
        problemClassifier: $push: [{name: name, func: classifier}]
    else
      otherClassifiers = _.filter @state.problemClassifier, (classifierObject) ->
        classifierObject.name != name
      @setState update @state,
        problemClassifier: $set: otherClassifiers

  filterProblems: (problems) ->
    visibleProblems = _.filter problems, ((problem) ->
      (@state.filterRegex.exec problem.name) != null and _.all (classifier.func problem for classifier in @state.problemClassifier)
    ).bind this

    sortedProblems = _.sortBy visibleProblems, @state.activeSort.name

    if @state.activeSort.ascending
      sortedProblems
    else
      sortedProblems.reverse()

  render: ->
    filteredProblems = @filterProblems @props.problems
    <Row className="pad">
      <Col xs={3} md={3}>
        <Row>
          <ProblemFilter onSortChange={@onSortChange} filter="" activeSort={@state.activeSort} onFilterChange={@onFilterChange}/>
        </Row>
        <Row>
          <ProblemClassifierList setClassifier={@setClassifier} problems={filteredProblems}
            bundles={@props.bundles}/>
        </Row>
        <Row>
          <ProblemDependencyView bundles={@props.bundles} onProblemChange={@props.onProblemChange}/>
        </Row>
      </Col>
      <Col xs={9} md={9}>
        <Row>
          <Col xs={12}>
            <ProblemListModifiers problems={filteredProblems} onProblemChange={@props.onProblemChange}/>
          </Col>
        </Row>
        <Row>
          <Col xs={12}>
            <ProblemList problems={filteredProblems} submissions={@props.submissions} onProblemChange={@props.onProblemChange}/>
          </Col>
        </Row>
      </Col>
    </Row>
