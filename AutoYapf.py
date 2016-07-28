import os
import subprocess
import sys

import sublime
import sublime_plugin

# FIXME: rename, as autoyapf is no longer accurate


class Formatter(object):
    def format_text(self, text):
        raise NotImplementedError

    @classmethod
    def popen(cls, *args, **kwargs):
        startupinfo = None
        if sys.platform in ('win32', 'cygwin'):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = (subprocess.CREATE_NEW_CONSOLE
                                   | subprocess.STARTF_USESHOWWINDOW)
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # set language/encoding to utf8
        env = kwargs.pop('env', {}) or os.environ.copy()
        env['LANG'] = 'utf-8'

        return subprocess.Popen(*args, startupinfo=startupinfo, **kwargs)


class YapfFormatter(Formatter):
    def format_text(self, text):
        cmd = ['yapf', '--verify']

        popen = self.popen(cmd,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           stdin=subprocess.PIPE)

        stdout, stderr = popen.communicate(text.encode('utf-8'))

        # since yapf>=0.3: 0 unchanged, 2 changed
        if popen.returncode not in (0, 2):
            error_lines = stderr.decode('utf-8').strip().replace(
                '\r\n', '\n').split('\n')
            loc, msg = error_lines[-4], error_lines[-1]
            loc = loc[loc.find('line'):]
            sublime.status_message('yapf: {} @ {}'.format(msg, loc))
            return

        new_text = stdout.decode('utf-8').replace('\r\n', '\n')

        return new_text


class RustFmtFormatter(Formatter):
    def format_text(self, text):
        cmd = [os.path.expanduser('~/.cargo/bin/rustfmt'), '--skip-children']

        popen = self.popen(cmd,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           stdin=subprocess.PIPE)

        stdout, stderr = popen.communicate(text.encode('utf8'))
        if popen.returncode != 0:
            sublime.status_message('rustfmt failed')
            return

        new_text = stdout.decode('utf-8').replace('\r\n', '\n')

        return new_text


class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        view.run_command('auto_yapf')


class AutoYapfCommand(sublime_plugin.TextCommand):
    def guess_lang(self):
        if self.view.score_selector(0, 'source.python') > 0:
            return 'python'
        if self.view.score_selector(0, 'source.rust') > 0:
            return 'rust'

    def is_enabled(self):
        return self.guess_lang() is not None

    def run(self, edit):
        # determine current text
        selection = sublime.Region(0, self.view.size())

        formatter = {
            'python': YapfFormatter,
            'rust': RustFmtFormatter,
        }[self.guess_lang()]()
        current_text = self.view.substr(selection)
        new_text = formatter.format_text(current_text)

        if new_text is not None:
            self.view.replace(edit, selection, new_text)
