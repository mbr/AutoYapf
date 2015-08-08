from contextlib import contextmanager
import os
import subprocess
import tempfile

import sublime
import sublime_plugin


@contextmanager
def temporary_file(*args, **kwargs):
    ignore_unlinked = kwargs.pop('ignore_unliked', False)

    fp = tempfile.NamedTemporaryFile(*args, delete=False, **kwargs)
    try:
        yield fp
    finally:
        try:
            os.unlink(fp.name)
        except OSError as e:
            # if the file does not exist anymore, ignore
            if e.errno != 2 or ignore_unlinked is False:
                raise


class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        view.run_command('auto_yapf')


class AutoYapfCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        is_python = self.view.score_selector(0, 'source.python') > 0
        return is_python

    def run(self, edit):
        selection = sublime.Region(0, self.view.size())
        bytes = self.view.substr(selection).encode('utf-8')

        # dump source into temporary file
        with temporary_file(suffix='.py') as fp:
            name = fp.name
            fp.write(bytes)

            # run yapf
            args = ['yapf', '--verify', '--in-place', name]
            env = os.environ.copy()
            env['LANG'] = 'utf-8'
            popen = subprocess.Popen(args,
                                     env=env,
                                     stderr=subprocess.PIPE,
                                     shell=True)
            _, stderr = popen.communicate()
            if popen.returncode:
                error_lines = stderr.decode('utf-8').strip().replace(
                    '\r\n', '\n').split('\n')
                loc, msg = error_lines[-4], error_lines[-1]
                loc = loc[loc.find('line'):]
                sublime.status_message('yapf: %s @ %s' % (msg, loc))
                return

            # read back in
            new_text = open(name, 'rb').read().decode('utf-8').replace('\r\n',
                                                                       '\n')

        # replace it
        self.view.replace(edit, selection, new_text)
