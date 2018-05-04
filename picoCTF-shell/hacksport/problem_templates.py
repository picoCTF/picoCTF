"""
High Level Problem API.
"""

import os
from copy import copy

from hacksport.problem import Compiled, File, ProtectedFile, Remote


def CompiledBinary(makefile=None,
                   compiler="gcc",
                   sources=None,
                   binary_name=None,
                   is_32_bit=True,
                   executable_stack=True,
                   no_stack_protector=True,
                   aslr=False,
                   compiler_flags=copy([]),
                   flag_file=None,
                   static_flag=None,
                   share_source=False,
                   remote=False):
    """
    Creates a challenge for a compiled binary. User must specify either a makefile
    or compiler sources. If a makefile is specified, the binary name must also be
    provided. If a flag_file is not provided, it will default to flag.txt. If the
    given flag file does not exist, it will be created. If share_source is set to
    true, all files specified in sources will be copied to the deployment
    directory. If remote is set to true, the challenge will be assigned a port and
    be wrapped in a server.

    Keyword Args:
        makefile: The name of the makefile. Defualts to None.
        compiler: The compiler to be used. Defaults to gcc.
        sources: The list of source files. Defaults to [].
        binary_name: The name of the output binary. Defaults to the same name as sources[0].
        is_32_bit: Specifies if the output binary should be 32 bit. Only works nicely with gcc as the compiler.
                   Defaults to True.
        executable_stack: Specifies if the output binary should have an executable stack. Only works nicely with gcc as the compiler.
                          Defaults to True.
        no_stack_protector: Specifies if the output binary should opt out of stack canaries. Only works nicely with gcc as the compiler.
                            Defaults to True.
        aslr: Specifies if the output binary should have aslr or not. Only used if the challenge is remote.
                            Defaults to False.
        compiler_flags: The list of any additional compiler flags to be passed. Defaults to [].
        flag_file: The name of the flag file. If it does not exist, it will be created. Defaults to flag.txt
        static_flag: A string containing the static flag. If specified, the flag generation will always return this. Defaults to None.
        remote: Specifies if the challenge should be remote or not. Defaults to False.
    """

    if is_32_bit and "-m32" not in compiler_flags:
        compiler_flags.append("-m32")
    if executable_stack and "-zexecstack" not in compiler_flags:
        compiler_flags.append("-zexecstack")
    if no_stack_protector and "-fno-stack-protector" not in compiler_flags:
        compiler_flags.append("-fno-stack-protector")

    if makefile is None and sources is None:
        assert False, "You must provide either a makefile or a sources list"

    if sources is None:
        assert binary_name is not None, "You must provide the binary name if you use a makefile"

    if flag_file is None:
        flag_file = "flag.txt"

    base_classes = [Compiled]
    if remote:
        base_classes.append(Remote)

    class Problem(*base_classes):
        files = copy([])

        remove_aslr = not aslr

        if share_source:
            files = copy([File(source) for source in sources])

        if binary_name is not None:
            program_name = binary_name
        else:
            program_name = os.path.splitext(sources[0])[0]

        def __init__(self):
            self.makefile = makefile
            self.compiler = compiler
            self.compiler_sources = sources
            self.compiler_flags = compiler_flags

            if not os.path.isfile(flag_file):
                with open(flag_file, "w") as f:
                    f.write("{{flag}}\n")

            if static_flag is not None:
                self.generate_flag = lambda random: static_flag

            self.files.append(ProtectedFile(flag_file))

    return Problem
