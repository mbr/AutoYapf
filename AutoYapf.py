import os
import subprocess

import sublime
import sublime_plugin
import sys

# FIXME: rename, as autoyapf is no longer accurate


def popen_wincompat(*args, **kwargs):
    startupinfo = None
    if sys.platform in ('win32', 'cygwin'):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = (subprocess.CREATE_NEW_CONSOLE
                               | subprocess.STARTF_USESHOWWINDOW)
        startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.Popen(*args, startupinfo=startupinfo, **kwargs)


class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        view.run_command('auto_yapf')


class AutoYapfCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        is_python = self.view.score_selector(0, 'source.python') > 0
        return is_python

    def run(self, edit):
        # determine current text
        selection = sublime.Region(0, self.view.size())

        current_text = self.view.substr(selection)

        # set language to utf8
        env = os.environ.copy()
        env['LANG'] = 'utf-8'

        # run yapf
        cmd = ['yapf', '--verify']

        popen = popen_wincompat(cmd,
                                env=env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE)

        stdout, stderr = popen.communicate(current_text.encode('utf-8'))

        # since yapf>=0.3: 0 unchanged, 2 changed
        if popen.returncode not in (0, 2):
            error_lines = stderr.decode('utf-8').strip().replace(
                '\r\n', '\n').split('\n')
            loc, msg = error_lines[-4], error_lines[-1]
            loc = loc[loc.find('line'):]
            sublime.status_message('yapf: %s @ %s' % (msg, loc))
            return

        # replace current by new text
        new_text = stdout.decode('utf-8').replace('\r\n', '\n')
        self.view.replace(edit, selection, new_text)
