const { Badge, Button, ButtonGroup, ButtonToolbar, Glyphicon, Col, Input, ListGroup,
        ListGroupItem, NavItem, Panel, PanelGroup, ProgressBar, Row, Tab,
        Table, Tabs } = ReactBootstrap;
const { update } = React.addons;


const renderAchievementMessage = _.template(
  $("#achievement-message-template")
    .remove()
    .text()
);

window.ratingMetrics = ["Difficulty", "Enjoyment", "Educational Value"];
window.ratingQuestion = {
  Difficulty: "How difficult is this problem?",
  Enjoyment: "Did you enjoy this problem?",
  "Educational Value": "How much did you learn while solving this problem?"
};
window.ratingChoices = {
  Difficulty: ["Too easy", "", "A bit challenging", "", "Very hard"],
  Enjoyment: ["Hated it!", "", "It was okay.", "", "Loved it!"],
  "Educational Value": [
    "Nothing at all",
    "",
    "Something useful",
    "",
    "Learned a lot!"
  ]
};

window.timeValues = [
  "5 minutes or less",
  "10 minutes",
  "20 minutes",
  "40 minutes",
  "1 hour",
  "2 hours",
  "3 hours",
  "4 hours",
  "5 hours",
  "6 hours",
  "8 hours",
  "10 hours",
  "15 hours",
  "20 hours",
  "30 hours",
  "40 hours or more"
];

const sanitizeMetricName = metric => metric.toLowerCase().replace(" ", "-");

const constructAchievementCallbackChainHelper = function(achievements, index) {
  $(".modal-backdrop").remove();
  if (index >= 0) {
    messageDialog(
      renderAchievementMessage({ achievement: achievements[index] }),
      "Achievement Unlocked!",
      "OK",
      () => constructAchievementCallbackChainHelper(achievements, index - 1)
    );
  }
};

const constructAchievementCallbackChain = achievements =>
  constructAchievementCallbackChainHelper(
    achievements,
    achievements.length - 1
  );

// apiCall "GET", "/api/v1/achievements"
// .done (data) ->
//   if data['status'] is 1
//     new_achievements = (x for x in data.data when !x.seen)
//     constructAchievementCallbackChain new_achievements

const addProblemReview = function(e) {
  const target = $(e.target);

  const pid = target.data("pid");
  const feedback = {
    liked: target.data("setting") === "up"
  };

  const postData = { feedback, pid };
  apiCall("POST", "/api/v1/feedback", postData)
    .done(function(data) {
      apiNotify({ status: 1, message: "Your feedback has been accepted." });
      const selector = `#${pid}-thumbs${feedback.liked ? "down" : "up"}`;
      $(selector).removeClass("active");
      target.addClass("active");
      gtag('event', 'Review', {
        'event_category': 'Problem',
        'event_label': 'Basic'
      });
    })
    .fail(jqXHR =>
      apiNotify({ status: 0, message: jqXHR.responseJSON.message })
    );
};

// apiCall "GET", "/api/v1/achievements"
// .done (data) ->
//   if data['status'] is 1
//     new_achievements = (x for x in data.data when !x.seen)
//     constructAchievementCallbackChain new_achievements

const updateScoreStats = selector => {
  drawTeamProgressionGraph("#team-progression-graph");
  apiCall("GET", "/api/v1/team/score").done(function (data) {
    if (data) {
      $(selector)
        .children("#team-score")
        .remove();
      $(selector).append(
        `<span id='team-score' class='pull-right'>Score: ${data.score}</span>`
      );
    }
  });
};

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

    const solvedState = _.groupBy(this.props.problems, "solved");
    let solvedData = _.map(solvedState, (problems, solved) => ({
      name: solved == 'true' ? "Solved" : "Unsolved",
      size: problems.length,
      classifier(problem) {
        return problem.solved.toString() === solved;
      }
    }));
    //solvedData = _.sortBy(solvedData, "name");

    return (
      <PanelGroup className="problem-classifier" collapsible={true}>
        <ProblemClassifier
          {...Object.assign(
            { name: "Categories", data: categoryData },
            this.props
          )}
        />
        <ProblemClassifier
          {...Object.assign(
            { name: "Solved", data: solvedData },
            this.props
          )}
        />
      </PanelGroup>
    );
  }
});

const ProblemHintTable = React.createClass({
  render() {
    return (
      <ListGroup>
        <div className="panel-body">
          {this.props.hints.map((hint, i) => (
            <ListGroupItem key={i} dangerouslySetInnerHTML={ {__html: hint} }/>
          ))}
        </div>
      </ListGroup>
    );
  }
});

const ProblemSubmit = React.createClass({
  getInitialState() {
    return {
      value : ""
    }
  },
  handleChange(e) {
    this.setState({ value: e.target.value })
  },
  submitProblem (e) {
   e.preventDefault();
   const input = $(e.target).find("input");
   apiCall("POST", "/api/v1/submissions", {
     pid: this.props.pid,
     key: this.state.value,
     method: "web"
   })
     .done(data => {
       if (data.correct) {
         gtag('event', 'Solve', {
           'event_category': 'Problem',
           'event_label': 'Basic'
         });
         apiNotify({ status: 1, message: data.message });
         this.setState({value: ""});
         this.props.toggleExpand();
         this.props.updateProblemsList();
       } else {
         gtag('event', 'Wrong', {
           'event_category': 'Problem',
           'event_label': 'Basic'
         });
         apiNotify({ status: 0, message: data.message });
       }
     })
     .fail(jqXHR =>
       apiNotify({ status: 0, message: jqXHR.responseJSON.message })
     );
  },

  dockerCreate (e) {
    e.preventDefault();
    $(e.target).html("Loading...")

    const target = $(e.target);
    const instanceDigest = target.data("value");
    const doUpdate = this.props.updateProblemsList;
    apiCall("POST", "/api/v1/docker/" + instanceDigest, {})
      .done(function(data) {
        apiNotify(data);
        doUpdate();
      })
      .fail(jqXHR =>
        apiNotify({ status: 0, message: jqXHR.responseJSON.message })
      );
  },

  dockerStop (e) {
    e.preventDefault();
    const target = $(e.target);
    const instanceDigest = target.data("digest");
    const containerID = target.data("cid");
    const doUpdate = this.props.updateProblemsList;
    apiCall("DELETE", "/api/v1/docker/" + instanceDigest + "/" + containerID, {})
      .done(function(data) {
        apiNotify(data);
        doUpdate();
      })
      .fail(jqXHR =>
        apiNotify({ status: 0, message: jqXHR.responseJSON.message })
      );
  },

  dockerReset (e) {
    const target = $(e.target);
    const instanceDigest = target.data("digest");
    const containerID = target.data("cid");
    const doUpdate = this.props.updateProblemsList;
    apiCall("PUT", "/api/v1/docker/" + instanceDigest + "/" + containerID, {})
      .done(function(data) {
        apiNotify(data);
        doUpdate();
      })
      .fail(jqXHR =>
        apiNotify({ status: 0, message: jqXHR.responseJSON.message })
      );
  },

  renderPorts() {
      return (
      <div>
        {
        this.props.container['ports'].map((port, index) => {
         return (
              <p className="problem-description"><strong>{port.desc}</strong>: <span dangerouslySetInnerHTML={ {__html: port.msg}}></span></p>
           )
      })
        }
      </div>)
   },

  render() {
    const submitButton = (<Button className="btn-primary" type="submit">Submit!</Button>);
    const upButton = (
      <Button
        id={this.props.pid + "-thumbsup"}
        data-pid={this.props.pid}
        data-setting="up"
        style={{borderRadius: 0, top:0}}
        className={`rating-button glyphicon glyphicon-thumbs-up pull-left ${this.props.thumbs.upClass}`}
        onClick={addProblemReview}
      />
    );
    const downButton = (
      <Button
        id={this.props.pid + "-thumbsdown"}
        data-pid={this.props.pid}
        data-setting="down"
        style={{top:0}}
        className={`rating-button glyphicon glyphicon-thumbs-down pull-right ${this.props.thumbs.downClass}`}
        onClick={addProblemReview}
      />
    );

    const createContainer = (
      <Button
        id={this.props.pid + "-docker-create"}
        data-value={this.props.instance_digest}
        className="btn btn-success btn-sm"
        onClick={(e) => this.dockerCreate(e)}
      >
      Start Challenge
      </Button>
    );


    var docker = (
      <Row className="form-group">
        <Col className="text-center">
            {createContainer}
        </Col>
      </Row>
    );

    var style={justifyContent:"center", display: "flex"};

    if (this.props.container ){
      docker  = (
      <Row className="form-group">
        <ButtonToolbar style={style}>
        <ButtonGroup>
            <Button
              id={this.props.pid + "-docker-reset"}
              data-digest={this.props.instance_digest}
              data-cid={this.props.container['cid']}
              className="btn btn-warning btn-sm"
              onClick={(e) => this.dockerReset(e)}
            >
            Reset
            </Button>
        </ButtonGroup>
        <ButtonGroup>
            <Button
              id={this.props.pid + "-docker-stop"}
              data-digest={this.props.instance_digest}
              data-cid={this.props.container['cid']}
              className="btn btn-danger btn-sm"
              onClick={(e) => this.dockerStop(e)}
            >
            Stop
            </Button>
        </ButtonGroup>
        </ButtonToolbar>
      </Row>
      )
    };

    return (
      <Col>
        <p className="problem-description" dangerouslySetInnerHTML={ {__html: this.props.description} }></p>
        {this.props.container && this.renderPorts()}
        {this.props.docker_challenge && docker}
        <form className="problem-submit" onSubmit={this.submitProblem}>
          <Row>
            <Input
              buttonBefore={submitButton}
              type="text"
              value={this.state.value}
              placeholder="RTD{FLAG}"
              onChange={this.handleChange}
            >
              <span className="input-group-btn">
                {upButton}
              </span>
              <span className="input-group-btn">
                {downButton}
              </span>
            </Input>
          </Row>
        </form>
      </Col>
    )
  }
});

const Problem = React.createClass({
  getInitialState() {
    if (this.props.solved) {
      return { expanded: false };
    } else {
      return { expanded: true };
    }
  },

  handleExpand(e) {
    if (e) { e.preventDefault(); }
    this.setState({ expanded: !this.state.expanded });
  },

  render() {
    const problemHeader = (
      <div>
        <span className="do-expand">
          {this.props.name} - Points: {this.props.score} - (Solves: {this.props.solves})
        </span>
        <div className="pull-right">
          {this.props.category} - {this.props.solved ? "Solved" : "Unsolved"}
        </div>
      </div>
    );

    //Do something interesting here.
    const panelStyle = this.props.disabled ? "default" : "default";

    var alreadyReviewed = false;
    var review = null;

    for (let i = 0; i < this.props.reviewData.length; i++)
      if (this.props.reviewData[i].pid === this.props.pid){
        alreadyReviewed = true;
        review = this.props.reviewData[i].feedback;
      }

    const thumbs = {
      upClass: alreadyReviewed && review.liked ? "active" : "",
      downClass: alreadyReviewed && !review.liked ? "active" : ""
    };

    if (this.state.expanded && this.props.hints.length > 0) {
      return (
        <Panel
          bsStyle={panelStyle}
          header={problemHeader}
          collapsible={true}
          expanded={this.state.expanded}
          onSelect={this.handleExpand}
        >
          <Tabs defaultActiveKey={this.props.pid + "solve"} bsStyle="tabs">
            <Tab eventKey={this.props.pid + "solve"} title="Solve">
              <div className="panel-body">
                <ProblemSubmit
                  {...Object.assign(
                    {
                      thumbs: thumbs,
                      updateProblemsList: this.props.updateProblemsList,
                      toggleExpand: this.handleExpand
                    },
                    this.props
                  )}
                />
              </div>
            </Tab>
            <Tab eventKey={this.props.pid + "hint"} title="Hints">
              <ProblemHintTable hints={this.props.hints} />
            </Tab>
          </Tabs>
        </Panel>
      );
    } else if (this.state.expanded && this.props.hints.length == 0) {
      return (
        <Panel
          bsStyle={panelStyle}
          header={problemHeader}
          collapsible={true}
          expanded={this.state.expanded}
          onSelect={this.handleExpand}
        >
          <Tabs defaultActiveKey={this.props.pid + "solve"} bsStyle="tabs">
                <Tab eventKey={this.props.pid + "solve"} title="Solve">
                  <div className="panel-body">
                  <ProblemSubmit
                    {...Object.assign(
                      {
                        thumbs: thumbs,
                        toggleExpand: this.handleExpand
                      },
                      this.props
                    )}
                  />
                  </div>
                </Tab>
          </Tabs>
        </Panel>
      );
    } else {
      return (
        <Panel
          bsStyle={panelStyle}
          header={problemHeader}
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
              No matching problems are available.
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
                reviewData: this.props.reviewData,
                updateProblemsList: this.props.updateProblemsList
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

const ProblemView = React.createClass({
  getInitialState() {
    return {
      reviewData: [],
      filterRegex: /.*/,
      activeSort: {
        name: "score",
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

  componentDidMount() {
    this.updateFeedback();
  },

  updateFeedback() {
    apiCall("GET", "/api/v1/feedback")
      .done(data => {
        this.setState({ reviewData: data });
      })
      .fail(jqXHR =>
        apiNotify({ status: 0, message: jqXHR.responseJSON.message })
      );
  },

  onFilterChange(filter) {
    try {
      const newFilter = new RegExp(filter, "i");
      this.setState({ filterRegex: newFilter });
    } catch (error) {}
  },
  // We shouldn't do anything.

  onSortChange(name, ascending) {
    this.setState({ activeSort: { name, ascending }})
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
      this.setState({ problemClassifier: otherClassifiers });
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
            />
          </Row>
        </Col>
        <Col md={9}>
          <ProblemList
            problems={filteredProblems}
            reviewData={this.state.reviewData}
            updateProblemsList={this.props.updateProblemsList}
          />
        </Col>
      </Row>
    );
  }
});

const ProblemProgress = React.createClass({
  getInitialState() {
    return {
      team: {},
      user: {}
    };
  },
  componentDidMount() {
    apiCall("GET", "/api/v1/team")
      .done(data => {
        this.setState({ team: data })
      })
      .fail(jqXHR =>
        apiNotify({ status: 0, message: jqXHR.responseJSON.message })
      );

    addAjaxListener("problemInfoState", "/api/v1/user", data => {
      this.setState({ user: data });
    });
  },

  render() {
    let panelHeader;
    const allProblemsByCategory = _.groupBy(this.props.problems, "category");
    const solvedProblemsByCategory = _.groupBy(
      this.props.solvedProblems,
      "category"
    );

    const categories = _.keys(allProblemsByCategory);

    const styles = ["success", "info", "primary", "warning", "danger"];

    const glyphs = {
      Cryptography: "/img/lock.svg",
      "Web Exploitation": "/img/browser.svg",
      "Binary Exploitation": "/img/binary.svg",
      "Reverse Engineering": "/img/reversecog.svg",
      Forensics: "/img/search.svg",
      Tutorial: "/img/laptop.svg"
    };

    if (
      this.state.team &&
      this.state.team.length > 0 &&
      this.state.user.username !== this.state.team.team_name &&
      this.state.team.team_name.length > 0
    ) {
      panelHeader = (
        <div>
          Category Overview
          <span className="pull-right">
            Team: <b>{this.state.team.team_name}</b>
          </span>
        </div>
      );
    } else {
      panelHeader = <div>Category Overview</div>;
    }

    return (
      <Panel header={panelHeader}>
        {categories.map(function(category, i) {
          const currentlySolved = solvedProblemsByCategory[category]
            ? solvedProblemsByCategory[category].length
            : 0;
          return (
            <Row key={i}>
              <Col sm={8} md={6} lg={8} className="progress-container">
                <ProgressBar
                  now={currentlySolved}
                  bsStyle={styles[i % styles.length]}
                  max={allProblemsByCategory[category].length}
                  label="%(now)s / %(max)s"
                />
              </Col>
              <Col sm={4} md={6} lg={4} className="progress-label">
                <img
                  className="category-icon"
                  src={glyphs[category] ? glyphs[category] : "/img/laptop.svg"}
                />
                <div className="pull-right">{category}</div>
              </Col>
            </Row>
          );
        })}
      </Panel>
    );
  }
});


const ProblemRoot = React.createClass({
  getInitialState() {
    return {
      problems: [],
      solvedProblems: [],
    };
  },

  componentDidMount() {
    this.updateProblemsList()
  },

  updateProblemsList() {
    updateScoreStats("#title");
    apiCall("GET", "/api/v1/problems")
      .done(data => {
        this.setState({ problems: data });
        this.setState({ solvedProblems: data.filter(problem => problem.solved) });
      })
      .fail(jqXHR =>
        apiNotify({ status: 0, message: jqXHR.responseJSON.message })
      );
  },

  render() {
    let progressHeader = (<div><Glyphicon glyph="stats"/>{" Progress Tracker"}</div>);
    return (
      <div>
        <Row>
          <Panel header={progressHeader} defaultExpanded={false} collapsible={true}>
            <Row>
              <Col md={6}>
                <ProblemProgress
                  problems={this.state.problems}
                  solvedProblems={this.state.solvedProblems}
                />
              </Col>
              <Col md={6}>
                <Panel header="Score Progression over Time">
                  <div id="team-progression-graph"/>
                </Panel>
              </Col>
            </Row>
          </Panel>
        </Row>
        <Row>
          <ProblemView
            problems={this.state.problems}
            updateProblemsList={this.updateProblemsList}
          />
        </Row>
      </div>
    );
  }
});


$(() => {
    ReactDOM.render(<ProblemRoot />, document.getElementById("problem-root-holder"));
});
