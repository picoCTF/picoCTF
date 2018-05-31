from hacksport.problem import (Compiled, ExecutableFile, File, ProtectedFile,
                               Remote)


class Problem(Remote, Compiled):
    program_name = "mybinary"
    makefile = "Makefile"
    files = [File("mybinary.c"), ProtectedFile("flag.txt")]
    secret = "test"

    def __init__(self):
        self.lucky = self.random.randint(0, 1000)
