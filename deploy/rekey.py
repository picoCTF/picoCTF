#!/usr/bin/env python3

import crypt
import os
import random
import string
import sys
import hmac
import hashlib
import subprocess
import getpass

try:
    from ruamel.yaml import YAML  # supports round-tripping yaml
    from ruamel.yaml.comments import CommentedSeq  # sometimes we get this instead of normal lists
except ImportError:
    print('\n*** Please install ruamel.yaml with `pip install "ruamel.yaml>0.15"` ***\n\n', file=sys.stderr)
    raise


def sha512_crypt(password, salt=None, rounds=None):
    '''This is used in place of `mkpasswd --sha-512`'''
    if salt is None:
        rand = random.SystemRandom()
        salt = ''.join([rand.choice(string.ascii_letters + string.digits)
                        for _ in range(8)])

    prefix = '$6$'
    if rounds is not None:
        rounds = max(1000, min(999999999, rounds or 5000))
        prefix += 'rounds={0}$'.format(rounds)
    return crypt.crypt(password, prefix + salt)

# known good, default found in vault.yml
# known to fail on windows (but WSL works)
assert sha512_crypt('CHANGE_AND_REKEY', salt='vGd1X7SV') == '$6$vGd1X7SV$yeT9KeCiRudYnbyUfdxgUqDcFUS1XoFZaNoBAypXyYbfSiHnWpg6SQUWWiGK2ux8BFO70Uk2uycUuzX/H7ExA1', "mkpasswd implementation failed, try on Linux instead"


def rekey_vault(vault):
    '''uses ansible-vault to rekey vault file (without changing contents'''
    cmd = ['ansible-vault', 'rekey', vault]
    subprocess.check_call(cmd)


def start_edit_vault(vault):
    '''tells ansible-vault to edit the vault using this script as the $EDITOR'''
    cmd = ['ansible-vault', 'edit', vault]
    env = os.environ.copy()
    env['EDITOR'] = __file__ + " --edit"
    subprocess.check_call(cmd, env=env)

def edit_tmpvault(filename):
    '''Update yaml config and by changing any key with the value CHANGE_AND_REKEY

    requests a master password and uses pbkdf2 to get a master key to base all
    of the new keys off of
    '''
    yaml = YAML()
    with open(filename) as fobj:
        vault_dict = yaml.load(fobj)
    master_pass = getpass.getpass("Enter master key to generate values: ").encode('utf-8')
    master_key = hashlib.pbkdf2_hmac('sha256', master_pass, os.urandom(16), 100000)
    change_values(vault_dict, 'CHANGE_AND_REKEY', master_key)
    with open(filename, 'w') as fobj:
        yaml.dump(vault_dict, fobj)

def new_key(label, hmac_key):
    '''calculate a new key for using the master key and the current label (variable name)
    '''
    result = hmac.new(hmac_key, label.encode('utf-8'), hashlib.sha256).hexdigest()
#    result = base64.b64encode(hmac.new(hmac_key, label.encode('utf-8'), hashlib.sha256).digest(), '-_').decode('ascii').rstrip('=')
    print("GOT NEW: KEY FOR LABEL: %r" % (label,))
    return result

def change_values(vault_dict, old_key, master_key, parent_k=None):
    '''
    Change values in the vault dictionary, recursively

    mainly looks at top level keys, but also looks at lists of dicts
    recursively (but not lists)

    Also includes slight hack to support `mkpasswd` output with special
    handling for labels ending in _crypt
    '''
    extra_keys = {}
    for k in vault_dict.keys():
        v = vault_dict[k]
        if isinstance(v, list) or isinstance(v, CommentedSeq):
            for i, vv in enumerate(v):
                if hasattr(vv, 'keys'):
                    change_values(vv, old_key, master_key, parent_k='%s-%s' % (k, i))
        if v == old_key or k.endswith('_crypt'):
            print("CHANGING KEY FOR LABEL: %r (parent: %r)" % (k, parent_k))
            key = new_key(k if parent_k is None else parent_k, master_key)
            if k.endswith('_crypt'):
                vault_dict[k] = sha512_crypt(key[8:], salt=key[:8])
                extra_keys[k + '_clear'] = key[8:]  # add the key in the clear for easy lookup by an admin with the vault key
            else:
                vault_dict[k] = key
    vault_dict.update(extra_keys)
            

if __name__ == '__main__':
    if sys.argv[1] == '--edit':
        edit_tmpvault(sys.argv[2])
        sys.exit(0)
    rekey_vault(vault=sys.argv[1])
    start_edit_vault(sys.argv[1])
    sys.exit(0)
