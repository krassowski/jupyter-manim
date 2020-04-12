import inspect
import pickle
import re
from typing import NamedTuple

import pytest
from papermill import execute_notebook

from jupyter_manim import ManimMagics, find_ipython_frame
import jupyter_manim


SHAPES_EXAMPLE = """
from manimlib.scene.scene import Scene
from manimlib.mobject.geometry import Circle
from manimlib.animation.creation import ShowCreation

class Shapes(Scene):

    def construct(self):
        circle = Circle()
        self.play(ShowCreation(circle))
"""


SHAPES_OUTPUT_REGEXP = r"""
    <video
      width="854"
      height="480"
      autoplay="autoplay"
      controls
    >
        <source src="videos/(.*?)/1440p60/Shapes\.mp4" type="video/mp4">
    </video>
"""


@pytest.mark.manim_dependent
def test_integration():
    output_notebook = execute_notebook(
        'Example.ipynb',
        'Example_result.ipynb',
    )
    for cell in output_notebook['cells']:
        assert cell['metadata']['papermill']['exception'] is False

    last_cell_outputs = output_notebook['cells'][-1]['outputs']
    if len(last_cell_outputs) != 1:
        print(last_cell_outputs)
    assert len(last_cell_outputs) == 1
    output_data = last_cell_outputs[0]['data']
    assert re.match(
        # the example notebook uses low quality option for faster rendering
        SHAPES_OUTPUT_REGEXP.replace('/1440p60/', '/480p15/'),
        output_data['text/html']
    )


class MockFrameInfo(NamedTuple):
    filename: str


def test_find_ipython_frame():
    ipython_frame = MockFrameInfo(filename='<ipython-input-918-9c9a2cba73bf>')
    parent_frame = MockFrameInfo(filename='/venv/lib/python3.7/site-packages/IPython/core/interactiveshell.py')

    frame = find_ipython_frame([ipython_frame, parent_frame])
    assert frame is ipython_frame

    frame = find_ipython_frame([parent_frame])
    assert frame is None


PICKLE_A = 'this should be pickled '
_PICKLE_B = 'this should not'


def test_pickle(monkeypatch):
    magics_manager = ManimMagics()

    def mock_frame(stack):
        """Return the frame of test_pickle"""
        return inspect.stack()[0]

    monkeypatch.setattr(jupyter_manim, 'find_ipython_frame', mock_frame)

    with magics_manager.export_globals() as pickled_file:
        assert type(pickled_file) is str
        assert pickled_file.endswith('.pickle')

        with open(pickled_file, 'rb') as f:
            unpickled = pickle.load(f)

        assert 'PICKLE_A' in unpickled
        assert unpickled['PICKLE_A'] == PICKLE_A
        assert '_PICKLE_B' not in unpickled


def test_imports(monkeypatch):
    magics_manager = ManimMagics()

    def mock_frame(stack):
        """Return the frame of test_pickle"""
        return inspect.stack()[0]

    monkeypatch.setattr(jupyter_manim, 'find_ipython_frame', mock_frame)
    imports = magics_manager.extract_imports()
    assert 'import pickle' in imports


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


@pytest.mark.manim_dependent
def test_cell_magic():
    magics_manager = ManimMagics()
    result = magics_manager.manim('Shapes', SHAPES_EXAMPLE)
    assert re.match(SHAPES_OUTPUT_REGEXP, result.data)


@pytest.mark.manim_dependent
def test_cell_base64():
    magics_manager = ManimMagics()
    result = magics_manager.manim('Shapes --base64 --low_quality', SHAPES_EXAMPLE)
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


@pytest.mark.manim_dependent
def test_cell_base64_gif():
    magics_manager = ManimMagics()
    result = magics_manager.manim(
        'Shapes --base64 --low_quality --save_as_gif',
        SHAPES_EXAMPLE
    )
    assert re.match(r"""
    <img
      width="854"
      height="480"
      src="data:image/gif;base64,(.*?)"
    >
    """, result.data)


@pytest.mark.manim_dependent
def test_cell_gif():
    magics_manager = ManimMagics()
    result = magics_manager.manim(
        'Shapes --low_quality --save_as_gif',
        SHAPES_EXAMPLE
    )

    assert re.match(r"""
    <img
      width="854"
      height="480"
      src="(.*?)/Shapes\.gif"
    >
    """, result.data)
