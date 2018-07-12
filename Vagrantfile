# -*- mode: ruby -*-
# vi: set ft=ruby :

# TODO:
# - mount_options looks really fishy
# - use double quote correctly

require 'etc'

# Extract suffix if working directory starts with prefix; otherwise return "".
def compute_auto_name_suffix(prefix = "picoCTF")
  dirname = File.basename(Dir.getwd)
  return dirname.start_with?(prefix) ? dirname[prefix.length..-1] : ""
end

Vagrant.configure("2") do |config|
  config.vm.define "shell", primary: true do |shell|
    shell.vm.box = "ubuntu/xenial64"
    shell.vm.network "private_network", ip: "192.168.2.3"

    shell.vm.synced_folder ".", "/vagrant", disabled: true
    shell.vm.synced_folder ".", "/picoCTF",
                           owner: "vagrant", group: "vagrant",
                           mount_options: ["dmode=775", "fmode=775"]

    shell.vm.provision "shell", path: "vagrant/provision_scripts/install_ansible.sh"
    shell.vm.provision :ansible_local do |ansible|
      ansible.compatibility_mode = "2.0"
      ansible.playbook = "site.yml"
      ansible.limit = "shell"
      ansible.provisioning_path = "/picoCTF/ansible/"
      ansible.inventory_path = "/picoCTF/ansible/inventories/local_development"
    end

    shell.vm.provider "virtualbox" do |vb|
      vb.name = "picoCTF-shell-dev" + compute_auto_name_suffix()
      # Overridable settings
      vb.cpus = [(ENV['J'] || '1').to_i, Etc.nprocessors].min
      vb.gui = ENV['G']
      vb.memory = (ENV['M'] || '2').to_i * 1024
      # Others
      vb.customize [
        "modifyvm", :id,
        "--uartmode1", "file", File.join(Dir.pwd, vb.name + "-console.log")
      ]
    end
  end

  config.vm.define "web", primary: true do |web|
    web.vm.box = "ubuntu/xenial64"
    web.vm.network "private_network", ip: "192.168.2.2"

    web.vm.synced_folder ".", "/vagrant", disabled: true
    web.vm.synced_folder ".", "/picoCTF",
                         owner: "vagrant", group: "vagrant",
                         mount_options: ["dmode=775", "fmode=775"]

    web.vm.provision "shell", path: "vagrant/provision_scripts/install_ansible.sh"
    web.vm.provision :ansible_local do |ansible|
      ansible.compatibility_mode = "2.0"
      ansible.playbook = "site.yml"
      ansible.limit = ["db", "web"]
      ansible.provisioning_path = "/picoCTF/ansible/"
      ansible.inventory_path = "/picoCTF/ansible/inventories/local_development"
    end

    web.vm.provider "virtualbox" do |vb|
      vb.name = "picoCTF-web-dev" + compute_auto_name_suffix()
      # Overridable settings
      vb.cpus = [(ENV['J'] || '1').to_i, Etc.nprocessors].min
      vb.gui = ENV['G']
      vb.memory = (ENV['M'] || '1').to_i * 1024
      # Others
      vb.customize [
        "modifyvm", :id,
        "--uartmode1", "file", File.join(Dir.pwd, vb.name + "-console.log")
      ]
    end
  end
end
