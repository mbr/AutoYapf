import os
import subprocess

import sublime
import sublime_plugin


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
        args = ['yapf', '--verify']
        env = os.environ.copy()
        env['LANG'] = 'utf-8'

        popen = subprocess.Popen(
            args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE)
        yapf_result, stderr = popen.communicate(bytes)

        if popen.returncode:
            error_lines = stderr.decode('utf-8').strip().replace(
                '\r\n', '\n').split('\n')
            loc, msg = error_lines[-4], error_lines[-1]
            loc = loc[loc.find('line'):]
            sublime.status_message('yapf: %s @ %s' % (msg, loc))
            return

        new_text = yapf_result.decode('utf-8').replace('\r\n', '\n')

        # replace it
        self.view.replace(edit, selection, new_text)
