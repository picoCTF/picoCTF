apiOffline =
  News: "/news"

teacherLoggedIn =
  Problems: "/problems"
  Shell: "/shell"
  Scoreboard: "/scoreboard"
  Stats: "/stats"
  Classroom: "/classroom"
  News: "/news"

teacherLoggedInNoCompetition =
  Scoreboard: "/scoreboard"
  Classroom: "/classroom"
  Stats: "/stats"
  News: "/news"

userLoggedIn =
  Problems: "/problems"
  Shell: "/shell"
  Scoreboard: "/scoreboard"
  Stats: "/stats"
  News: "/news"

userLoggedInNoCompetition =
  Scoreboard: "/scoreboard"
  Stats: "/stats"
  News: "/news"

userNotLoggedIn =
  Stats: "/stats"
  News: "/news"

adminLoggedIn =
  Management: "/management"

loadNavbar = (renderNavbarLinks, renderNestedNavbarLinks) ->

  navbarLayout = {
    renderNavbarLinks: renderNavbarLinks,
    renderNestedNavbarLinks: renderNestedNavbarLinks
  }

  apiCall "GET", "/api/user/status", {}
  .done (data) ->
    navbarLayout.links = userNotLoggedIn
    navbarLayout.status = data.data
    navbarLayout.topLevel = true
    if data["status"] == 1
      if not data.data["logged_in"]
        $(".show-when-logged-out").css("display", "inline-block")
      if data.data["teacher"]
        if data.data["competition_active"]
           navbarLayout.links = teacherLoggedIn
        else
           navbarLayout.links = teacherLoggedInNoCompetition
      else if data.data["logged_in"]
         if data.data["competition_active"]
            navbarLayout.links = userLoggedIn
         else
            navbarLayout.links = userLoggedInNoCompetition

        if data.data["admin"]
           $.extend navbarLayout.links, adminLoggedIn

    $("#navbar-links").html renderNavbarLinks(navbarLayout)
    $("#navbar-item-logout").on("click", logout)

  .fail ->
    navbarLayout.links = apiOffline
    $("#navbar-links").html renderNavbarLinks(navbarLayout)

$ ->
  renderNavbarLinks = _.template($("#navbar-links-template").remove().text())
  renderNestedNavbarLinks = _.template($("#navbar-links-dropdown-template").remove().text())

  loadNavbar(renderNavbarLinks, renderNestedNavbarLinks)
