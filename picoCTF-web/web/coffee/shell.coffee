renderShellServers = _.template($("#shell-servers-template").remove().text())

$ ->
  apiCall "GET", "/api/user/shell_servers", {}

  .done (resp) ->
    switch resp.status
      when 0
          apiNotify resp
      when 1
        if resp.data
          $("#shell-servers").html renderShellServers({servers: resp.data})
