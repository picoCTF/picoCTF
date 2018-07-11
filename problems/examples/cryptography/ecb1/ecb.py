#!/usr/bin/env python3
import os
import sys
import base64

from Crypto.Cipher import AES

flag = open("flag", "r").read().strip()
key = open("key", "r").read().strip()

welcome = """
{{welcome_message}}
"""


def encrypt():
    cipher = AES.new(base64.b16decode(key, casefold=True), AES.MODE_ECB)
    return base64.b16encode(cipher.encrypt(flag))

# flush output immediately
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w')
print(welcome)
print("KEY: " + key)
print("MESSAGE: " + encrypt().decode())
