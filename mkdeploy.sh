#!/usr/bin/env bash
SZ="        1"
set -x
set -e

# Note:
# choose to use bundle when git is available at deployment time (like on AWS)
# otherwise use zip, it's smaller, but requires python at deployment time to
# extract, which isn't always available.  Bundle is also nice while development.
# Read more below.
#
#
# Example of end-to-end build & deploy
#
# ### Build
#
# # builds a zip from a specific commit (ie. HEAD or maybe tag v1.2.3) ignoring the working directory
# ./mkdeploy.sh zip HEAD
#
# Alternately, build a git bundle.  Better if python/unzip is unavailable.  git is on AWS by default
#
# # builds a bundle from a specific commit (ie. HEAD or maybe tag v1.2.3) ignoring the working directory
# ./mkdeploy.sh bundle HEAD
#
# Alternately, build a git bundle INCLUDING the working directory by saving a stash in the bundle
#
# # This is good for testing changes to the deployment processes, inventory variables, etc
# ./mkdeploy.sh bundle stash
#
# ### Deploy
#
# # Easy mode, assumes 'pico_db' exists in the inventory at ansible/inventories/my_inventory
# DEPLOY_ANSIBLE_INVENTORYNAME=my_inventory \
# DEPLOY_ANSIBLE_LIMIT=db \
# ./dist/dist.zip push pico_db
#
# # Or maybe you made a bundle and you want to deploy more than 1 role
# # And include some extra options to ansible-playbook
# DEPLOY_ANSIBLE_INVENTORYNAME=my_inventory \
# DEPLOY_ANSIBLE_LIMIT=db,web \
# ./dist/dist.bundle push pico_web_and_db -e extra=option -vv
#
# # You can also move the distribution somewhere yourself, and run it like so:
# ssh -t target "sudo DEPLOY_ANSIBLE_INVENTORYNAME=my_inventory DEPLOY_ANSIBLE_LIMIT=web ~/dist.zip"
#
# # Later...
#
# # If something went wrong, or you just want to re-run the ansible playbook the same way as it was deployed:
# ssh -t target "sudo /picoCTF/deploy_this.sh"

# # Or you can add extra options now too
# ssh -t target "sudo /picoCTF/deploy_this.sh -vv"


if [ "$1" == "bundle" ]; then
    REF="$2"
    ME="$0"
    if [ "$REF" == "stash" ]; then
        echo "I AM: $0"
        if [ "$0" != "/tmp/me" ]; then
            cp "$0" /tmp/me
            chmod 755 /tmp/me
            exec /tmp/me "$@"
        else
            ME="$0"
            shift;
        fi
        git stash --include-untracked
        git tag -f temp-stash stash@{0}
        git stash pop
        REF="HEAD temp-stash"
    fi
    mkdir -p dist
    git bundle create dist/dist._bundle $REF
    if [ "$REF" == "HEAD temp-stash" ]; then
        git tag -d temp-stash
    fi
    head -n1 $ME > dist/dist.bundle
    SZ=$(stat --printf="%s" $ME)
    printf "SZ=\"% 9d\"\n" $SZ >> dist/dist.bundle
    tail -n+3 $ME >> dist/dist.bundle
    cat dist/dist._bundle >> dist/dist.bundle
    chmod 755 dist/dist.bundle
    exit 0
fi
if [ "$1" == "zip" ]; then
    mkdir -p dist
    head -n1 $0 > dist/dist.zip
    SZ=$(stat --printf="%s" $0)
    printf "SZ=\"% 9d\"\n" $SZ >> dist/dist.zip
    tail -n+3 $0 >> dist/dist.zip
    git archive --format zip $2 >> dist/dist.zip
    chmod 755 dist/dist.zip
    exit 0
fi

echo "Deploying Role(s): ${DEPLOY_ANSIBLE_LIMIT:?Need to set DEPLOY_ANSIBLE_LIMIT}"
echo "   From Inventory: ${DEPLOY_ANSIBLE_INVENTORYNAME:?Need to set DEPLOY_ANSIBLE_INVENTORYNAME}"
HERE=$(pwd)

if [ "$1" == "push" ]; then
    ME=$(basename $0)
    TARGET=$2
    INVENTORY="ansible/inventories/${DEPLOY_ANSIBLE_INVENTORYNAME}"
    [ -e ansible/inventories/${DEPLOY_ANSIBLE_INVENTORYNAME} ] || (echo no inventory found; exit 1)
    HOSTNAME=$(grep $TARGET ${INVENTORY} | head -n1 | cut -d '=' -f4 | cut -d ' ' -f1)
    HOSTNAME=${HOSTNAME:?HOSTNAME not found from inventory}
    scp $0 ubuntu@$HOSTNAME:~/
    shift;
    shift;
    CMD=$(echo ssh -t ubuntu@$HOSTNAME sudo bash -c \"DEPLOY_ANSIBLE_INVENTORYNAME=$DEPLOY_ANSIBLE_INVENTORYNAME DEPLOY_ANSIBLE_LIMIT=$DEPLOY_ANSIBLE_LIMIT "~/$ME" $@ \")
    exec $CMD
fi

# extract to /picoCTF

python -mzipfile -e $0 /picoCTF ||
(
dd if=$0 iflag=skip_bytes skip=$(($SZ)) of=/tmp/tmp.bundle &&
git clone --recursive --depth 1 /tmp/tmp.bundle /picoCTF &&
((cd /picoCTF && git stash store temp-stash && git stash branch temp-stash) || echo no stash found) &&
rm -rf /tmp/tmp.bundle
)

# initialize ansible

cd /picoCTF

cd ansible
# make sure inventory exists
[ -e ./inventories/${DEPLOY_ANSIBLE_INVENTORYNAME} ] || (echo no inventory found; exit 1)

# place deployment-specific files

# disable clone_repo subtasks
sed -i 's/when: private_repo/when: False/g' ./roles/common/tasks/clone_repo.yml
sed -i 's/when: not private_repo/when: False/g' ./roles/common/tasks/clone_repo.yml

# create reusable deploy_this.sh script

cat > /picoCTF/deploy_this.sh <<EOF_DEPLOY
#!/bin/sh
cd /picoCTF/ansible
exec ansible-playbook --vault-id @prompt -i $(pwd)/inventories/${DEPLOY_ANSIBLE_INVENTORYNAME} --limit="${DEPLOY_ANSIBLE_LIMIT}" $@ "\$@" site.yml
EOF_DEPLOY
chmod 755 /picoCTF/deploy_this.sh

# GO!

# install ansible

cd ..
bash vagrant/provision_scripts/install_ansible.sh </dev/null

# deploy
exec /picoCTF/deploy_this.sh

# Last Line
