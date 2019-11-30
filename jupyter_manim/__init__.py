import inspect
import os
import pickle
import sys
from contextlib import ExitStack, suppress, redirect_stdout, redirect_stderr, contextmanager
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch
from warnings import warn
import base64

import manimlib
from IPython import get_ipython
from IPython.core.magic import Magics, magics_class, cell_magic
from IPython.display import HTML

__version__ = 1.0

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


UNPICKLE_SCRIPT = """
import pickle
from warnings import warn
try:
    with open('{pickle_path}', 'rb') as f:
        objects_from_notebook = pickle.load(f)
except pickle.PickleError as e:
    warn('Could not unpickle the global objects from the notebook', e)

globals_dict = globals()

for name, object in objects_from_notebook.items():
    try:
        if name in globals_dict:
            warn('Import from notebook: ' + name + ' already in the globals(), skipping')
        else:
            globals_dict[name] = object
    except Exception as e:
        warn('Could save into a global variable', e)
"""


def is_pickable(obj):
    try:
        pickle.dumps(obj)
        return True
    except (pickle.PicklingError, TypeError, AttributeError):
        return False


def find_ipython_frame(frames):
    for frame in inspect.stack():
        if frame.filename.startswith('<ipython-input-'):
            return frame
    return None


@magics_class
class ManimMagics(Magics):
    path_line_start = 'File ready at '

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.defaults = {
            'autoplay': True,
            'controls': True,
            'remote': False,
            'silent': True,
            'width': 854,
            'height': 480,
            'export_variables': True
        }

    video_settings = {'width', 'height', 'controls', 'autoplay'}
    magic_off_switches = {
        'verbose': 'silent',
        'no-controls': 'controls',
        'no-autoplay': 'autoplay'
    }

    @contextmanager
    def export_globals(self):
        """Save pickable globals to a temporary file and yield its location"""
        f = NamedTemporaryFile('wb', suffix='.pickle', delete=False)
        try:
            # TODO: go over each of the variables, exclude dunders, test pickability

            frame = find_ipython_frame(inspect.stack())
            if not frame:
                raise Exception('Could not find IPython frame')

            globals_dict = frame[0].f_globals

            to_pickle = {
                name: obj
                for name, obj in globals_dict.items()
                if (not name.startswith('_')) and is_pickable(obj)
            }
            pickle.dump(to_pickle, f)
            f.close()
            yield f.name
        except Exception as e:
            warn('Pickling failed: ' + str(e))
            yield None
        finally:
            os.remove(f.name)

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
        
        remote_index = (
            user_args.index('-b') if '-b' in user_args else
            user_args.index('--base64') if '--base64' in user_args else
            None
        )
        if remote_index is not None:
            settings['remote'] = True
            if '-b' in user_args:
                user_args.remove('-b')
            if '--base64' in user_args:
                user_args.remove('--base64')
        
        silent = settings['silent']

        def catch_path_and_forward(lines):
            nonlocal path
            for line in lines.split('\n'):
                if not silent:
                    print(line, file=std_out)

                if line.startswith(self.path_line_start):
                    path = line[len(self.path_line_start):].strip()

        # Using a workaround for Windows permissions issue as in this questions:
        # https://stackoverflow.com/q/15169101
        f = NamedTemporaryFile('w', suffix='.py', delete=False)
        try:

            with ExitStack() as stack:

                enter = stack.enter_context

                if settings['export_variables']:
                    # TODO test this with pytest
                    pickle_path = enter(self.export_globals())

                    if pickle_path:
                        unpickle_script = UNPICKLE_SCRIPT.format(pickle_path=pickle_path)
                        cell = unpickle_script + cell

                f.write(cell)
                f.close()

                args = ['manim', f.name, *user_args]

                stdout = StringIOWithCallback(catch_path_and_forward)

                enter(patch.object(sys, 'argv', args))
                enter(suppress(SystemExit))
                enter(redirect_stdout(stdout))

                if silent:
                    stderr = StringIO()
                    enter(redirect_stderr(stderr))

                manimlib.main()
        finally:
            os.remove(f.name)

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
            # If in remote mode, we send with a data: url
            if settings['remote']:
                data = base64.b64encode(path.read_bytes()).decode()
                data_url = "data:video/mp4;base64," + data
                return video(data_url, **video_settings)
            # otherwise a relative path is fine
            else:
                return video(relative_path, **video_settings)
        else:
            just_show_help = '-h' in user_args or '--help' in user_args

            if not just_show_help:
                warn('Could not find path in the manim output')

            # If we were silent, some errors could have been silenced too.
            if silent:
                # Let's break the silence:
                print(stdout.getvalue())
                print(stderr.getvalue(), file=sys.stderr)


ip = get_ipython()
ip.register_magics(ManimMagics)
