renderGroupInformation = _.template($("#group-info-template").remove().text())

renderTeamSelection = _.template($("#team-selection-template").remove().text())

@groupListCache = []

String.prototype.hashCode = ->
	hash = 0
	for i in [0...@length]
 		char = @charCodeAt i
 		hash = ((hash << 5) - hash) + char
 		hash = hash & hash
 	hash

createGroupSetup = () ->
    formDialogContents = _.template($("#new-group-template").html())({})
    formDialog formDialogContents, "Create a New Classroom", "OK", "new-group-name", () ->
        createGroup($('#new-group-name').val())

@exportProblemCSV = (groupName, teams) ->
  apiCall "GET", "/api/problems/all" # New teacher-only route for problem names and categories ONLY
  .done ((resp) ->
    if resp.status == 0
      apiNotify resp
    else
      # problems = _.filter resp.data.problems, (problem) -> !problem.disabled
      problems = resp.data; # non-admin API only returns non-disabled problems as top level data array
      data = [["Teamname", "Usernames"].concat(_.map(problems, (problem) -> problem.name), ["Total"])]
      _.each teams, ((team) ->
        members = '"' + team.members.map((member) -> return member.username).join(", ") + '"'
        teamData = [team.team_name, members]
        teamData = teamData.concat _.map problems, ((problem) ->
          solved = _.find team.solved_problems, (solvedProblem) -> solvedProblem.name == problem.name
          return if solved then problem.score else 0
        )
        teamData = teamData.concat [team.score]
        data.push teamData
      )
      csvData = (_.map data, (fields) -> fields.join ",").join "\n"
      download(csvData, "#{groupName}.csv", "text/csv")
  )

loadGroupOverview = (groups, showFirstTab, callback) ->
  $("#group-overview").html renderGroupInformation({data: groups})

  $("#new-class-tab").on "click", (e) ->
    createGroupSetup()

  $("#new-class-button").on "click", (e) ->
    createGroupSetup()

  $("#class-tabs").on 'shown.bs.tab', 'a[data-toggle="tab"]', (e) ->
    tabBody = $(this).attr("href")
    groupName = $(this).data("group-name")

    apiCall "GET", "/api/group/member_information", {gid: $(this).data("gid")}
    .done (teamData) ->
        ga('send', 'event', 'Group', 'LoadTeacherGroupInformation', 'Success')
        for group in groups
          if `group.name == groupName` # coffee script will translate to === which doesn't work for numbers (e.g. 14741)
            $(tabBody).html renderTeamSelection({teams: teamData.data, groupName: groupName, owner: group.owner, gid: group.gid})
        $(".team-visualization-enabler").on "click", (e) ->
          tid = $(e.target).data("tid")
          for team in teamData.data
            if tid == team.tid
              preparedData = {status: 1, data: team.progression}
              window.renderTeamProgressionGraph("#visualizer-"+tid, preparedData)
              #hack
              _.delay window.renderTeamRadarGraph, 150, "#radar-visualizer-"+tid, tid

  if showFirstTab
    $('#class-tabs a:first').tab('show')


  $("ul.nav-tabs a").click ( (e) ->
    e.preventDefault();
    $(this).tab 'show'
  );

  $("#group-request-form").on "submit", groupRequest
  $(".delete-group-span").on "click", (e) ->
    deleteGroup $(e.target).data("group-name")

  if callback
    callback()

loadGroupInfo = (showFirstTab, callback) ->
  apiCall "GET", "/api/group/list", {}
  .done (data) ->
    switch data["status"]
      when 0
        apiNotify(data)
        ga('send', 'event', 'Group', 'GroupListLoadFailure', data.message)
      when 1
        window.groupListCache = data.data
        loadGroupOverview data.data, showFirstTab, callback

createGroup = (groupName) ->
  apiCall "POST",  "/api/group/create", {"group-name": groupName}
  .done (data) ->
    if data['status'] is 1
      closeDialog()
      ga('send', 'event', 'Group', 'CreateGroup', 'Success')
      apiNotify(data)
      loadGroupInfo(false, () ->
                     $('#class-tabs li:eq(-2) a').tab('show'))
    else
      ga('send', 'event', 'Group', 'CreateGroup', 'Failure::' + data.message)
      apiNotifyElement($("#new-group-name"), data)

deleteGroup = (groupName) ->
  confirmDialog("You are about to permanently delete this class. This will automatically remove your students from this class. Are you sure you want to delete this class?",
                "Class Confirmation", "Delete Class", "Cancel",
                () ->
                  apiCall "POST", "/api/group/delete", {"group-name": groupName}
                  .done (data) ->
                    apiNotify(data)
                    if data['status'] is 1
                      ga('send', 'event', 'Group', 'DeleteGroup', 'Success')
                      loadGroupInfo(true)
                    else
                      ga('send', 'event', 'Group', 'DeleteGroup', 'Failure::' + data.message)
               ,() ->
                  ga('send', 'event', 'Group', 'DeleteGroup', 'RejectPrompt'))

#Could be simplified without this function
groupRequest = (e) ->
  e.preventDefault()
  groupName = $("#group-name-input").val()
  createGroup groupName

$ ->
  if not window.userStatus
    apiCall "GET", "/api/user/status"
    .done () ->
      if not window.userStatus.teacher
        apiNotify {status: 1, message: "You are no longer a teacher."}, "/profile"
  else if not window.userStatus.teacher
      apiNotify {status: 1, message: "You are no longer a teacher."}, "/profile"

  loadGroupInfo(true)

  $(document).on 'shown.bs.tab', 'a[href="#group-overview-tab"]', () ->
    loadGroupInfo(true)

  return
