from hacksport.problem_templates import CompiledBinary

Problem = CompiledBinary(
    sources=["mybinary.c"],
    share_source=True,
    static_flag="this_is_the_flag",
    remote=True)
