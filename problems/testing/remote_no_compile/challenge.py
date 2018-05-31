from hacksport.problem import (Compiled, ExecutableFile, File, ProtectedFile,
                               Remote)


class Problem(Remote):
    program_name = "mybinary"
    files = [ProtectedFile("flag.txt")]
