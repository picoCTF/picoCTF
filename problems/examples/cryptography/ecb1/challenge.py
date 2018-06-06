import string

from hacksport.problem import ProtectedFile, Remote


class Problem(Remote):
    program_name = "ecb.py"
    files = [ProtectedFile("flag"), ProtectedFile("key")]

    def initialize(self):
        # generate random 32 hexadecimal characters
        self.enc_key = ''.join(
            self.random.choice(string.digits + 'abcdef') for _ in range(32))

        self.welcome_message = "Welcome to Secure Encryption Service version 1.{}".format(
            self.random.randint(0, 10))
