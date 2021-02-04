import re
from hacksport.problem import Service, ProtectedFile

class Problem(Service):
    files = [ProtectedFile("flag.txt")]

    def initialize(self):
        with open("/etc/vsftpd.conf","r+") as f:
            text = f.read()
            text = re.sub("banner_file=.+", "banner_file=" + self.directory + "/flag.txt", text)
            text = re.sub("listen_port=.+", "listen_port=" + str(self.port), text)
            f.seek(0)
            f.write(text)
            f.truncate()

        self.start_cmd = "/usr/sbin/vsftpd"

    def generate_flag(self, random):
        return "RTD{scan_all_the_things}"
