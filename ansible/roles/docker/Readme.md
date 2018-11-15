# Docker

This role installs `docker-ce` and `docker-compose` directly from the provider.
This ensures the most up to date version.

This playbook supports the following operating systems:

- Debian 9 (stretch)
- Ubuntu 16.04 (xenial)

Additional operating systems can be supported by setting a `distro_facts`
dictionary with a key that matches the `ansible_distribution + "_" + ansible_distribution_release`
and the relevant urls.

```
distro_facts:
  Debian_stretch:
    apt_key_url: ""
    apt_key_id: ""
    repo: ""
```

Currently the playbook installs `docker-compose` version `1.22.0`. This can be
changed by setting the following variables:

```
docker_compose_version: ""
docker_compose_checksum: ""
```
