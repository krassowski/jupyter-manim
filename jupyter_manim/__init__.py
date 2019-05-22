from IPython.core.magic import Magics, magics_class, cell_magic
from unittest.mock import patch
from tempfile import NamedTemporaryFile
import manimlib
from IPython.display import HTML
import sys
from io import StringIO
from contextlib import ExitStack, suppress, redirect_stdout, redirect_stderr
from warnings import warn
from IPython import get_ipython
from pathlib import Path

std_out = sys.stdout


def video(path, width=854, height=480, controls=True, autoplay=True):
    return HTML(f"""
    <video
      width="{width}"
      height="{height}"
      autoplay="{'autoplay' if autoplay else ''}"
      {'controls' if controls else ''}
    >
        <source src="{path}" type="video/mp4">
    </video>
    """)


class StringIOWithCallback(StringIO):

    def __init__(self, callback, **kwargs):
        super().__init__(**kwargs)
        self.callback = callback

    def write(self, s):
        super().write(s)
        self.callback(s)


@magics_class
class ManimMagics(Magics):
    path_line_start = 'File ready at '

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.defaults = {
            'autoplay': True,
            'controls': True,
            'silent': True,
            'width': 854,
            'height': 480
        }

    video_settings = {'width', 'height', 'controls', 'autoplay'}
    magic_off_switches = {
        'verbose': 'silent',
        'no-controls': 'controls',
        'no-autoplay': 'autoplay'
    }

    @cell_magic
    def manim(self, line, cell):
        # execute the code - won't generate any video, however it will introduce
        # the variables into the notebook's namespace (enabling autocompletion etc);
        # this also allows users to get feedback on some code errors early on
        get_ipython().ex(cell)

        user_args = line.split(' ')

        # path of the output video
        path = None

        settings = self.defaults.copy()

        # disable the switches as indicated by the user
        for key, arg in self.magic_off_switches.items():
            if '--' + key in user_args:
                user_args.remove('--' + key)
                settings[arg] = False

        resolution_index = (
            user_args.index('-r') if '-r' in user_args else
            user_args.index('--resolution') if '--resolution' in user_args else
            None
        )
        if resolution_index is not None:
            # the resolution is passed as "height,width"
            try:
                h, w = user_args[resolution_index + 1].split(',')
                settings['height'] = h
                settings['width'] = w
            except (IndexError, KeyError):
                warn('Unable to retrieve dimensions from your resolution setting, falling back to the defaults')

        silent = settings['silent']

        def catch_path_and_forward(lines):
            nonlocal path
            for line in lines.split('\n'):
                if not silent:
                    print(line, file=std_out)

                if line.startswith(self.path_line_start):
                    path = line[len(self.path_line_start):].strip()

        with NamedTemporaryFile('w', suffix='.py') as f:
            f.write(cell)
            f.flush()

            args = ['manim', f.name, *user_args]

            stdout = StringIOWithCallback(catch_path_and_forward)

            with ExitStack() as stack:

                enter = stack.enter_context

                enter(patch.object(sys, 'argv', args))
                enter(suppress(SystemExit))
                enter(redirect_stdout(stdout))

                if silent:
                    stderr = StringIO()
                    enter(redirect_stderr(stderr))

                manimlib.main()

        if path:
            path = Path(path)
            assert path.exists()

            # To display a video in Jupyter, we need to have access to it
            # so it has to be within the working tree. The absolute paths
            # are usually outside of the accessible range.
            relative_path = path.relative_to(Path.cwd())

            video_settings = {
                k: v
                for k, v in settings.items()
                if k in self.video_settings
            }

            return video(relative_path, **video_settings)
        else:
            warn('Could not find path in the manim output')

            # If we were silent, some errors could have been silenced too.
            if silent:
                # Let's break the silence:
                print(stdout.getvalue())
                print(stderr.getvalue(), file=sys.stderr)


ip = get_ipython()
ip.register_magics(ManimMagics)
