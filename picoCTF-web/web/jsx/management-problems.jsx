const { Panel } = ReactBootstrap;
const { Button } = ReactBootstrap;
const { ButtonGroup } = ReactBootstrap;
const { Glyphicon } = ReactBootstrap;
const { Col } = ReactBootstrap;
const { Input } = ReactBootstrap;
const { Label } = ReactBootstrap;
const { PanelGroup } = ReactBootstrap;
const { Row } = ReactBootstrap;
const { ListGroup } = ReactBootstrap;
const { ListGroupItem } = ReactBootstrap;
const { Collapse } = ReactBootstrap;
const { Table } = ReactBootstrap;

const { update } = React.addons;

const SortableButton = React.createClass({
  propTypes: {
    name: React.PropTypes.string.isRequired
  },

  handleClick(e) {
    this.props.onFocus(this.props.name);

    if (this.props.active) {
      this.props.onSortChange(this.props.name, !this.props.ascending);
    } else {
      //Make it active. No-op on sorting.
      this.props.onSortChange(this.props.name, this.props.ascending);
    }
  },

  render() {
    const glyph = this.props.ascending ? (
      <Glyphicon glyph="chevron-down" />
    ) : (
      <Glyphicon glyph="chevron-up" />
    );
    return (
      <Button
        bsSize="small"
        active={this.props.active}
        onClick={this.handleClick}
      >
        {this.props.name} {glyph}
      </Button>
    );
  }
});

const SortableButtonGroup = React.createClass({
  getInitialState() {
    const result = [];
    for (name of this.props.data) {
      result.push([name, { active: false, ascending: true }]);
    }
    const state = _.object(result);
    state[this.props.activeSort.name] = {
      active: true,
      ascending: this.props.activeSort.ascending
    };
    return state;
  },

  handleClick(name) {
    //Reset all active states.
    const activeStates = _.reduce(
      this.getInitialState(),
      function(memo, sortState, name) {
        memo[name] = { active: false, ascending: true };
        return memo;
      },
      {}
    );
    activeStates[name].active = true;
    this.setState(activeStates);
  },

  render() {
    const activeState = this.state;
    activeState[this.props.activeSort.name] = {
      active: true,
      ascending: this.props.activeSort.ascending
    };
    return (
      <ButtonGroup>
        {this.props.data.map((name, i) => {
          return (
            <SortableButton
              key={i}
              active={activeState[name].active}
              ascending={activeState[name].ascending}
              name={name}
              onSortChange={this.props.onSortChange}
              onFocus={this.handleClick}
            />
          );
        })}
      </ButtonGroup>
    );
  }
});

const ProblemFilter = React.createClass({
  propTypes: {
    onFilterChange: React.PropTypes.func.isRequired,
    filter: React.PropTypes.string
  },

  getInitialState() {
    return { filter: this.props.filter };
  },

  onChange() {
    const filterValue = this.refs.filter.getInputDOMNode().value;
    this.setState({ filter: filterValue });
    this.props.onFilterChange(filterValue);
  },

  render() {
    const glyph = <Glyphicon glyph="search" />;
    return (
      <Panel>
        <Col xs={12}>
          Search
          <Input
            type="text"
            className="form-control"
            ref="filter"
            addonBefore={glyph}
            onChange={this.onChange}
            value={this.state.filter}
          />
        </Col>
        <Col xs={12}>
          <SortableButtonGroup
            key={this.props.activeSort}
            activeSort={this.props.activeSort}
            onSortChange={this.props.onSortChange}
            data={["name", "category", "score"]}
          />
        </Col>
      </Panel>
    );
  }
});

const ProblemClassifierList = React.createClass({
  render() {
    const categories = _.groupBy(this.props.problems, "category");
    let categoryData = _.map(categories, (problems, category) => ({
      name: `Only ${category}`,
      size: problems.length,
      classifier(problem) {
        return problem.category === category;
      }
    }));
    categoryData = _.sortBy(categoryData, "name");

    const organizations = _.groupBy(this.props.problems, "organization");
    let organizationData = _.map(organizations, (problems, organization) => ({
      name: `Created by ${organization}`,
      size: problems.length,
      classifier(problem) {
        return problem.organization === organization;
      }
    }));
    organizationData = _.sortBy(organizationData, "name");

    const problemStates = _.countBy(this.props.problems, "disabled");
    const problemStateData = [];

    if (problemStates[false] > 0) {
      problemStateData.push({
        name: "Enabled problems",
        size: problemStates[false],
        classifier(problem) {
          return !problem.disabled;
        }
      });
    }

    if (problemStates[true] > 0) {
      problemStateData.push({
        name: "Disabled problems",
        size: problemStates[true],
        classifier(problem) {
          return problem.disabled;
        }
      });
    }

    return (
      <PanelGroup className="problem-classifier" collapsible={true}>
        <ProblemClassifier
          {...Object.assign(
            { name: "State", data: problemStateData },
            this.props
          )}
        />
        <ProblemClassifier
          {...Object.assign(
            { name: "Categories", data: categoryData },
            this.props
          )}
        />
        <ProblemClassifier
          {...Object.assign(
            { name: "Organizations", data: organizationData },
            this.props
          )}
        />
      </PanelGroup>
    );
  }
});

const ClassifierItem = React.createClass({
  handleClick(e) {
    this.props.setClassifier(
      !this.props.active,
      this.props.classifier,
      this.props.name
    );
    this.props.onExclusiveClick(this.props.name);
  },

  render() {
    const glyph = <Glyphicon glyph="ok" />;

    return (
      <ListGroupItem onClick={this.handleClick} className="classifier-item">
        {this.props.name} {this.props.active ? glyph : undefined}{" "}
        <div className="pull-right">
          <Badge>{this.props.size}</Badge>
        </div>
      </ListGroupItem>
    );
  }
});

const ProblemClassifier = React.createClass({
  getInitialState() {
    return _.object(
      this.props.data.map(classifier => [classifier.name, false])
    );
  },

  handleClick(name) {
    const activeStates = this.getInitialState();
    activeStates[name] = !this.state[name];
    this.setState(activeStates);
  },

  render() {
    return (
      <Panel header={this.props.name} defaultExpanded={true} collapsible={true}>
        <ListGroup fill={true}>
          {this.props.data.map((data, i) => {
            return (
              <ClassifierItem
                {...Object.assign(
                  {
                    onExclusiveClick: this.handleClick,
                    active: this.state[data.name],
                    key: i,
                    setClassifier: this.props.setClassifier
                  },
                  data
                )}
              />
            );
          })}
        </ListGroup>
      </Panel>
    );
  }
});

const CollapsibleInformation = React.createClass({
  getInitialState() {
    return { open: false };
  },

  toggleCollapse() {
    this.setState({ open: !this.state.open });
  },

  render() {
    const glyph = this.state.open ? "chevron-down" : "chevron-right";
    return (
      <div className="collapsible-information">
        <a onClick={this.toggleCollapse}>
          {this.props.title}{" "}
          <Glyphicon
            glyph={glyph}
            className="collapsible-information-chevron"
          />
        </a>
        <Collapse in={this.state.open}>{this.props.children}</Collapse>
      </div>
    );
  }
});

const ProblemFlagTable = React.createClass({
  render() {
    let sortedInstances = this.props.instances.sort((a, b) =>
      a.instance_number - b.instance_number
    );
    return (
      <Table responsive={true}>
        <thead>
          <tr>
            <th>#</th>
            <th>Instance</th>
            <th>Flag</th>
            {(() => {
              if (sortedInstances[0].port) {
                return (<th>Port</th>);
              }
            })()}
          </tr>
        </thead>
        <tbody>
          {sortedInstances.map((instance, i) => (
            <tr key={i}>
              <td>{instance.instance_number}</td>
              <td>{instance.iid}</td>
              <td>{instance.flag}</td>
            {(() => {
              if (instance.port) {
                return (<td>{instance.port}</td>);
              }
            })()}
            </tr>
          ))}
        </tbody>
      </Table>
    );
  }
});

const ProblemHintTable = React.createClass({
  render() {
    return (
      <Table responsive={true}>
        <thead>
          <tr>
            <th>#</th>
            <th>Hint</th>
          </tr>
        </thead>
        <tbody>
          {this.props.hints.map((hint, i) => (
            <tr key={i}>
              <td>{i + 1}</td>
              <td>{hint}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  }
});

const ProblemReview = React.createClass({
  render() {
    const style = {
      fontSize: "2.0em"
    };

    return (
      <Row>
        <Col sm={6} md={6} lg={6}>
          <div className="pull-right">
            <Glyphicon glyph="thumbs-up" className="active pad" style={style} />
            <Badge>{this.props.reviews.likes}</Badge>
          </div>
        </Col>
        <Col sm={6} md={6} lg={6}>
          <div className="pull-left">
            <Glyphicon
              glyph="thumbs-down"
              className="active pad"
              style={style}
            />
            <Badge>{this.props.reviews.dislikes}</Badge>
          </div>
        </Col>
      </Row>
    );
  }
});

const Problem = React.createClass({
  getInitialState() {
    return { expanded: false };
  },

  onStateToggle(e) {
    e.preventDefault();
    apiCall("PATCH", `/api/v1/problems/${this.props.pid}`, {
      disabled: !this.props.disabled
    }).done(this.props.onProblemChange);
  },

  handleExpand(e) {
    e.preventDefault();

    //This is awkward.
    if (
      $(e.target)
        .parent()
        .hasClass("do-expand")
    ) {
      this.setState({ expanded: !this.state.expanded });
    }
  },

  render() {
    let problemFooter;
    const statusButton = (
      <Button
        bsSize="xsmall"
        bsStyle={this.props.disabled ? "default" : "default"}
        onClick={this.onStateToggle}
      >
        {this.props.disabled ? "Enable" : "Disable"}{" "}
        <Glyphicon glyph={this.props.disabled ? "ok" : "minus"} />
      </Button>
    );

    const problemHeader = (
      <div>
        <span className="do-expand">
          {this.props.category} - {this.props.name}
        </span>
        <div className="pull-right">
          ({this.props.score}) {statusButton}
        </div>
      </div>
    );

    if (this.props.tags === undefined || this.props.tags.length === 0) {
      problemFooter = "No tags";
    } else {
      problemFooter = this.props.tags.map((tag, i) => (
        <Label key={i}>{tag}</Label>
      ));
    }

    //Do something interesting here.
    const panelStyle = this.props.disabled ? "default" : "default";

    const submissionDisplay =
      this.props.submissions &&
      this.props.submissions.valid + this.props.submissions.invalid >= 1 ? (
        <div>
          <h4 className="text-center"> Submissions </h4>
          <div style={{ width: "200px", height: "200px", margin: "auto" }}>
            <ProblemSubmissionDoughnut
              valid={this.props.submissions.valid}
              invalid={this.props.submissions.invalid}
              visible={this.state.expanded}
              className="text-center"
            />
          </div>
        </div>
      ) : (
        <p>No solve attempts.</p>
      );

    const reviewDisplay = <ProblemReview reviews={this.props.reviews} />;

    if (this.state.expanded) {
      return (
        <Panel
          bsStyle={panelStyle}
          header={problemHeader}
          footer={problemFooter}
          collapsible={true}
          expanded={this.state.expanded}
          onSelect={this.handleExpand}
        >
          <Row>
            <Col md={4}>
              {submissionDisplay}
              {reviewDisplay}
            </Col>
            <Col md={8}>
              <h4>
                {this.props.author}
                {this.props.organization
                  ? ` @ ${this.props.organization}`
                  : undefined}
              </h4>
              <hr />
              <CollapsibleInformation title="Description">
                <p className="problem-description">{this.props.description}</p>
              </CollapsibleInformation>
              <CollapsibleInformation title="Hints">
                <ProblemHintTable hints={this.props.hints} />
              </CollapsibleInformation>
              <CollapsibleInformation title={this.props.static_flag ? "Static Instance Flag" : "Instance Flags"}>
                <ProblemFlagTable instances={this.props.instances} />
              </CollapsibleInformation>
            </Col>
          </Row>
        </Panel>
      );
    } else {
      return (
        <Panel
          bsStyle={panelStyle}
          header={problemHeader}
          footer={problemFooter}
          collapsible={true}
          expanded={this.state.expanded}
          onSelect={this.handleExpand}
        />
      );
    }
  }
});

const ProblemList = React.createClass({
  propTypes: {
    problems: React.PropTypes.array.isRequired
  },

  render() {
    if (this.props.problems.length === 0) {
      return (
        <div className="panel">
          <h4>
            No problems have been loaded. Click <a href="#">here</a> to get
            started.
          </h4>
        </div>
      );
    }

    const problemComponents = this.props.problems.map((problem, i) => {
      return (
        <Col key={i} xs={12}>
          <Problem
            {...Object.assign(
              {
                key: problem.name,
                onProblemChange: this.props.onProblemChange,
                submissions: this.props.submissions[problem.name]
              },
              problem
            )}
          />
        </Col>
      );
    });

    return <Row>{problemComponents}</Row>;
  }
});

const ProblemDependencyView = React.createClass({
  handleClick(bundle) {
    apiCall("PATCH", `/api/v1/bundles/${bundle.bid}`, {
      dependencies_enabled: !bundle.dependencies_enabled
    }).done(this.props.onProblemChange);
  },

  render() {
    const bundleDisplay = this.props.bundles.map((bundle, i) => {
      const switchText = bundle.dependencies_enabled
        ? "Unlock Problems"
        : "Lock Problems";
      return (
        <ListGroupItem key={i} className="clearfix">
          <div>
            {bundle.name}
            <div className="pull-right">
              <Button
                bsSize="xsmall"
                onClick={this.handleClick.bind(null, bundle)}
              >
                {switchText}
              </Button>
            </div>
          </div>
        </ListGroupItem>
      );
    });

    return (
      <Panel header="Problem Dependencies">
        <p>{`By default, all problems are unlocked. You can enable or disable the problem unlock dependencies \
for your problem bundles below.`}</p>
        <ListGroup fill={true}>{bundleDisplay}</ListGroup>
      </Panel>
    );
  }
});

const ProblemListModifiers = React.createClass({
  onMassChange(enabled) {
    const change = enabled ? "enable" : "disable";
    const changeNumber = this.props.problems.length;
    window.confirmDialog(
      `Are you sure you want to ${change} these ${changeNumber} problems?`,
      "Mass Problem State Change",
      "Yes",
      "No",
      function() {
        const calls = _.map(this.props.problems, problem =>
          apiCall("PATCH", `/api/v1/problems/${problem.pid}`, {
            disabled: !enabled
          })
        );
        $.when.apply(this, calls).done(
          function() {
            if (
              _.all(_.map(arguments, call => _.first(call).success === true))
            ) {
              apiNotify({
                status: 1,
                message: "All problems have been successfully changed."
              });
            } else {
              apiNotify({
                status: 0,
                message: "There was an error changing some of the problems."
              });
            }
            this.props.onProblemChange();
          }.bind(this)
        );
      }.bind(this, () => false)
    );
  },

  render() {
    return (
      <Panel>
        <ButtonGroup className="pull-right">
          <Button onClick={this.onMassChange.bind(null, true)}>
            Enable All Problems
          </Button>
          <Button onClick={this.onMassChange.bind(null, false)}>
            Disable All Problems
          </Button>
        </ButtonGroup>
      </Panel>
    );
  }
});

const ProblemTab = React.createClass({
  propTypes: {
    problems: React.PropTypes.array.isRequired
  },

  getInitialState() {
    return {
      filterRegex: /.*/,
      activeSort: {
        name: "name",
        ascending: true
      },
      problemClassifier: [
        {
          name: "all",
          func(problem) {
            return true;
          }
        }
      ]
    };
  },

  onFilterChange(filter) {
    try {
      const newFilter = new RegExp(filter, "i");
      this.setState(
        update(this.state, { filterRegex: { $set: newFilter } })
      );
    } catch (error) {}
  },
  // We shouldn't do anything.

  onSortChange(name, ascending) {
    this.setState(
      update(this.state, { activeSort: { $set: { name, ascending } } })
    );
  },

  setClassifier(classifierState, classifier, name) {
    if (classifierState) {
      this.setState(
        update(this.state, {
          problemClassifier: { $push: [{ name, func: classifier }] }
        })
      );
    } else {
      const otherClassifiers = _.filter(
        this.state.problemClassifier,
        classifierObject => classifierObject.name !== name
      );
      this.setState(
        update(this.state, { problemClassifier: { $set: otherClassifiers } })
      );
    }
  },

  filterProblems(problems) {
    const visibleProblems = _.filter(problems, problem => {
      return (
        this.state.filterRegex.exec(problem.name) !== null &&
        _.all(
          this.state.problemClassifier.map(classifier =>
            classifier.func(problem)
          )
        )
      );
    });

    const sortedProblems = _.sortBy(
      visibleProblems,
      this.state.activeSort.name
    );

    if (this.state.activeSort.ascending) {
      return sortedProblems;
    } else {
      return sortedProblems.reverse();
    }
  },

  render() {
    const filteredProblems = this.filterProblems(this.props.problems);
    return (
      <Row className="pad">
        <Col md={3}>
          <Row>
            <ProblemFilter
              onSortChange={this.onSortChange}
              filter=""
              activeSort={this.state.activeSort}
              onFilterChange={this.onFilterChange}
            />
          </Row>
          <Row>
            <ProblemClassifierList
              setClassifier={this.setClassifier}
              problems={filteredProblems}
              bundles={this.props.bundles}
            />
          </Row>
          <Row>
            <ProblemDependencyView
              bundles={this.props.bundles}
              onProblemChange={this.props.onProblemChange}
            />
          </Row>
        </Col>
        <Col md={9}>
          <Row>
            <Col xs={12}>
              <ProblemListModifiers
                problems={filteredProblems}
                onProblemChange={this.props.onProblemChange}
              />
            </Col>
          </Row>
          <Row>
            <Col xs={12}>
              <ProblemList
                problems={filteredProblems}
                submissions={this.props.submissions}
                onProblemChange={this.props.onProblemChange}
              />
            </Col>
          </Row>
        </Col>
      </Row>
    );
  }
});
