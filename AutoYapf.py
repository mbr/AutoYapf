import os
import subprocess
import sys

import sublime
import sublime_plugin

# FIXME: rename, as autoyapf is no longer accurate


class FormatterError(Exception):
    pass


class Formatter(object):
    def format_text(self, text, target):
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
    def format_text(self, text, target):
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
            raise FormatterError('yapf: {} @ {}'.format(msg, loc))

        new_text = stdout.decode('utf-8').replace('\r\n', '\n')

        return new_text


class RustFmtFormatter(Formatter):
    def format_text(self, text, target):
        cmd = [os.path.expanduser('~/.cargo/bin/rustfmt'), '--skip-children']

        popen = self.popen(cmd,
                           cwd=os.path.dirname(target),
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           stdin=subprocess.PIPE)

        stdout, _ = popen.communicate(text.encode('utf8'))
        if popen.returncode != 0:
            raise FormatterError('rustfmt failed: {}'.format(stdout))

        new_text = stdout.decode('utf-8').replace('\r\n', '\n')

        return new_text


class TidyFormatter(Formatter):
    def format_text(self, text, target):
        cmd = ['tidy',
               '-utf8',
               '-q',
               '--clean',
               'yes',
               '--indent',
               'yes',
               '--indent-spaces',
               '2',
               '--indent-with-tabs',
               'no',
               '--drop-empty-elements',
               'no',
               '--drop-empty-paras',
               'no', ]

        popen = self.popen(cmd,
                           cwd=os.path.dirname(target),
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           stdin=subprocess.PIPE)

        stdout, stderr = popen.communicate(text.encode('utf8'))

        if stderr:
            print("tidy (status: {}) warnings: {}".format(popen.returncode,
                                                          stderr))

        # 0: all good, 1: warnigs, 2: errors
        if popen.returncode not in (0, 1):
            raise FormatterError('tidy failed: {}'.format(stdout))

        # for some reason, tidy adds trailing whitespace after <script>-tags
        new_text = ''.join(line.rstrip() + '\n'
                           for line in stdout.decode('utf-8').splitlines())

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
        if self.view.score_selector(0, 'text.html') > 0:
            return 'html'

    def is_enabled(self):
        return self.guess_lang() is not None

    def run(self, edit):
        fn = self.view.file_name()

        # determine current text
        selection = sublime.Region(0, self.view.size())

        formatter = {
            'python': YapfFormatter,
            'rust': RustFmtFormatter,
            'html': TidyFormatter,
        }[self.guess_lang()]()

        current_text = self.view.substr(selection)
        try:
            new_text = formatter.format_text(current_text, fn)
        except FormatterError as e:
            print('AutoYapf: Formatter failed: {}'.format(e))
            sublime.status_message(str(e))
        else:
            self.view.replace(edit, selection, new_text)
