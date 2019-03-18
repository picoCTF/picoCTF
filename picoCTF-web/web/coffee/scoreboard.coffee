renderScoreboardTeamScore = _.template($("#scoreboard-teamscore-template").remove().text())
renderScoreboardTabs = _.template($("#scoreboard-tabs-template").remove().text())
renderScoreboard = _.template($("#scoreboard-template").remove().text())
renderScorepage = _.template($("#scorepage-template").remove().text())


load_teamscore = ->
  apiCall "GET", "/api/team", {}
  .done (resp) ->
    switch resp["status"]
      when 1
        $("#scoreboard-teamscore").html renderScoreboardTeamScore({
          teamscore: resp.data.score
        })
      when 0
        apiNotify(resp)

@reloadGraph = ->
  reload = ->
    $(".progression-graph").empty()
    active_tab = $("ul#scoreboard-tabs li.active").data()
    if active_tab != undefined
      active_gid = active_tab.gid
      window.drawTopTeamsProgressionGraph "#"+active_gid+"-progression", active_gid

  setTimeout reload, 100

load_scoreboard_page = (boardname, page, tid) ->
  apiCall "GET", "/api/stats/scoreboard/" + boardname + "/" + page, {}
    .done (resp) ->
      switch resp["status"]
          when 1
            $('#' + boardname + " tbody").html(
              renderScorepage({
                scorepage: resp.data
                page:page
                tid: tid
              })
            )
          when 0
            apiNotify(resp)


load_scoreboard = ->
  apiCall "GET", "/api/stats/scoreboard", {}
  .done (resp) ->
    switch resp["status"]
      when 1
        $("#scoreboard-tabs").html(renderScoreboardTabs({
          data: resp.data,
          renderScoreboard: renderScoreboard
        })).promise().then( ->
          data = resp.data;
          paginate = ((board) ->
            $('#' + board.name + '-pagination').bootstrapPaginator({
              totalPages: board.pages,
              bootstrapMajorVersion: 3,
              numberOfPages: 10,
              currentPage: board.start_page,
              onPageClicked: ((e, eOriginal, type, page) ->
                load_scoreboard_page(board.name, page, data.tid)
              )
            })
          )
          Object.keys(data).forEach( (e) ->
            if Array.isArray(data[e])
              data[e].forEach(paginate)
            else if typeof(data[e]) == 'object'
              paginate(data[e])
          )
        )
        reloadGraph()
      when 0
        apiNotify(resp)

$ ->
  load_scoreboard()
  load_teamscore()
