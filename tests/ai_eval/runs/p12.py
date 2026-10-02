import kinemo as k

SRC = """
def square(x):
    result = x * x
    return result
"""


@k.scene
def code_highlight(s: k.Scene):
    code = k.Code(SRC, lang="python", line_numbers=True).place(at="center")
    s.play(k.write(code))
    s.play(code.highlight(lines=[2]))
    s.wait(1)
