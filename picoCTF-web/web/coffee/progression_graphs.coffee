numDataPoints = 720

divFromSelector = (selector) ->
  _.first($(selector))

borderColors = [
  "rgba(156,99,169,1)"
  "rgba(151,187,205,1)"
  "rgba(230,22,22,1)",
  "rgba(22,230,57,1)",
  "rgba(230,22,210,1)",
  "rgba(220,220,220,1)"
  "rgba(204,104,0,1)",
]

backgroundColors = [
  "rgba(156,99,169,0.2)",
  "rgba(151,187,205,0.2)",
  "rgba(230,22,22,0.2)",
  "rgba(22,230,57,0.2)",
  "rgba(230,22,210,0.2)",
  "rgba(220,220,220,0.2)",
  "rgba(204,104,0,0.2)",
]

scoreboardChartSettings =
  scales:
    yAxes: [
      gridLines:
        display: false
    ]
    xAxes: [
      gridLines:
        display: false
    ]

teamChartSettings =
  scales:
    yAxes: [
      gridLines:
        display: false
    ]
    xAxes: [
      gridLines:
        display: false
    ]


timestampsToBuckets = (samples, key, min, max, seconds) ->

  bucketNumber = (number) ->
    Math.floor((number - min) / seconds)

  continuousBucket = {}
  maxBuckets = bucketNumber max

  for i in [0..maxBuckets]
    continuousBucket[i] = []

  buckets = _.groupBy samples, (sample) ->
    bucketNumber sample[key]

  return _.extend continuousBucket, buckets

maxValuesFromBucketsExtended = (buckets, sampleKey) ->
  maxValues = []

  lastInsertedValue = 0

  _.each buckets, (samples) ->
    values = _.pluck(samples, sampleKey)

    if values.length > 0
      maxValue = _.max values
      maxValues.push maxValue
      lastInsertedValue = maxValue
    else
      maxValues.push lastInsertedValue

  return maxValues

progressionDataToPoints = (data, dataPoints, currentDate = 0) ->

  sortedData = _.sortBy _.flatten(data), (submission) ->
    return submission.time

  min = _.first(sortedData).time - 60*5
  lastTime = _.last(sortedData).time
  max = if currentDate is 0 then lastTime else Math.min(lastTime + 3600*24, currentDate)
  bucketWindow = Math.max(Math.floor((max - min) / dataPoints), 1)

  dataSets = []

  _.each data, (teamData) ->
    buckets = timestampsToBuckets teamData, "time", min, max, bucketWindow
    steps = maxValuesFromBucketsExtended buckets, "score"

    if steps.length > dataPoints
      steps = _.rest(steps, steps.length - dataPoints)

    dataSets.push steps

  #Avoid returning a two dimensional array with 1 element
  return if dataSets.length > 1 then dataSets else _.first(dataSets)

@drawTopTeamsProgressionGraph = (selector, gid) ->
  div = divFromSelector selector

  drawgraph = (data) ->
    apiCall "GET", "/api/time", {}
    .done (timedata) ->
      if data.data.length >= 2 && $(selector).is(":visible")
        scoreData = (team.score_progression for team in data.data)

        #Ensure there are submissions to work with
        if _.max(_.map(scoreData, (submissions) -> submissions.length)) > 0

          dataPoints = progressionDataToPoints scoreData, numDataPoints, timedata.data

          datasets = []
          for points,i in dataPoints
            datasets.push
              label: data.data[i].name
              data: points
              pointBackgroundColor: borderColors[i % borderColors.length]
              borderColor: borderColors[i % borderColors.length]
              backgroundColor: backgroundColors[i % backgroundColors.length]
              pointHitRadius: 0
              pointRadius: 1
              lineTension: 0

          data =
            labels: ("" for i in [1..numDataPoints])
            datasets: datasets

          $(div).empty()
          canvas = $("<canvas>").appendTo(div)

          canvas.attr('width', $(div).width())
          canvas.attr('height', $(div).height())

          chart = new Chart(_.first(canvas).getContext("2d"), {
              type: 'line',
              data: data,
              options: scoreboardChartSettings
          });

  if gid == "student"
    apiCall "GET", "/api/stats/top_teams/score_progression", {}
    .done drawgraph
  else if gid == "global"
    apiCall "GET", "/api/stats/top_teams/score_progression", {show_ineligible: true}
    .done drawgraph
  else
    apiCall "GET", "/api/stats/group/score_progression", {gid:gid}
    .done drawgraph

@renderTeamRadarGraph = (selector, tid) ->
  div = divFromSelector selector
  $(div).empty()
  radarData = window.generateRadarData(tid)
  if radarData.labels.length > 0
    canvas = $("<canvas>").appendTo(div)
    canvas.attr('width', $(div).width())
    canvas.attr('height', 400)

    chart = new Chart(_.first(canvas).getContext("2d"), {
              type: 'radar',
              data: radarData,
              options: { scale: { ticks: { beginAtZero: true } } }
            });
  else
    $("<p>Waiting for solved problems.</p>").appendTo div

@renderTeamProgressionGraph = (selector, data) ->
  div = divFromSelector selector
  apiCall "GET", "/api/time", {}
  .done (timedata) ->
    if data.status == 1
      if data.data.length > 0

        dataPoints = progressionDataToPoints [data.data], numDataPoints, timedata.data

        datasets = [
            label: "Score"
            data: dataPoints
            pointBackgroundColor: borderColors[0]
            borderColor: borderColors[0]
            backgroundColor: backgroundColors[0]
            pointHitRadius: 0
            pointRadius: 0
            lineTension: 0
        ]

        data =
          labels: ("" for i in [1..numDataPoints])
          datasets: datasets

        $(div).empty()
        canvas = $("<canvas>").appendTo(div)

        canvas.attr('width', $(div).width())
        canvas.attr('height', $(div).height())

        chart = new Chart(_.first(canvas).getContext("2d"), {
              type: 'line',
              data: data,
              options: teamChartSettings
        });

      else
          $(selector).html("<p>No problems have been solved.</p>")
    else
        $(selector).html("<p>No problems have been solved.</p>")

@drawTeamProgressionGraph = (selector, container_selector) ->
  apiCall "GET", "/api/stats/team/score_progression", {}
  .done (data) ->
    renderTeamProgressionGraph selector, data
