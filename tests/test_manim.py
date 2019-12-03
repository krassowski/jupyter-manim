import re

from jupyter_manim import ManimMagics


def test_pickle():
    # TODO
    pass


def test_arguments_resolution():
    magics_manager = ManimMagics()
    settings, user_args = magics_manager.parse_arguments('-r 100,200')
    assert settings['height'] == '100'
    assert settings['width'] == '200'

    settings, user_args = magics_manager.parse_arguments('--resolution 100,200')
    assert settings['height'] == '100'
    assert settings['width'] == '200'


def test_arguments_base64():
    magics_manager = ManimMagics()
    settings, user_args = magics_manager.parse_arguments('')
    assert not settings['remote']

    settings, user_args = magics_manager.parse_arguments('-b')
    assert settings['remote']

    settings, user_args = magics_manager.parse_arguments('--base64')
    assert settings['remote']


def test_arguments_silent():
    magics_manager = ManimMagics()
    settings, user_args = magics_manager.parse_arguments('')
    assert settings['silent']

    settings, user_args = magics_manager.parse_arguments('--verbose')
    assert not settings['silent']


def test_help(capsys):
    magics_manager = ManimMagics()
    magics_manager.manim('-h', '')
    captured = capsys.readouterr()
    assert captured.out.startswith('usage: manim')
    assert not captured.err.strip()


SHAPES_EXAMPLE = """
from manimlib.scene.scene import Scene
from manimlib.mobject.geometry import Circle
from manimlib.animation.creation import ShowCreation

class Shapes(Scene):

    def construct(self):
        circle = Circle()
        self.play(ShowCreation(circle))
"""


def test_cell_magic():
    magics_manager = ManimMagics()
    result = magics_manager.manim('Shapes', SHAPES_EXAMPLE)
    assert re.match(r"""
    <video
      width="854"
      height="480"
      autoplay="autoplay"
      controls
    >
        <source src="videos/(.*?)/1440p60/Shapes\.mp4" type="video/mp4">
    </video>
    """, result.data)


def test_cell_base64():
    magics_manager = ManimMagics()
    result = magics_manager.manim('Shapes --base64', SHAPES_EXAMPLE)
    assert re.match(r"""
    <video
      width="854"
      height="480"
      autoplay="autoplay"
      controls
    >
        <source src="data:video/mp4;base64,(.*?)" type="video/mp4">
    </video>
    """, result.data)
