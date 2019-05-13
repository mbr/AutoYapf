import os
import subprocess
import sys

import sublime
import sublime_plugin

# FIXME: rename, as autoyapf is no longer accurate

CONFIGURATION_KEY = "autoyapf_enabled"


class FormatterError(Exception):
    pass


class Formatter(object):
    def format_text(self, text, target):
        raise NotImplementedError

    @classmethod
    def popen(cls, *args, **kwargs):
        startupinfo = None
        if sys.platform in ("win32", "cygwin"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags = (
                subprocess.CREATE_NEW_CONSOLE | subprocess.STARTF_USESHOWWINDOW
            )
            startupinfo.wShowWindow = subprocess.SW_HIDE

        # set language/encoding to utf8
        env = kwargs.pop("env", {}) or os.environ.copy()
        env["LANG"] = "utf-8"

        return subprocess.Popen(*args, startupinfo=startupinfo, **kwargs)


class YapfFormatter(Formatter):
    def format_text(self, text, target):
        cmd = ["python3", "-m", "yapf"]

        popen = self.popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )

        stdout, stderr = popen.communicate(text.encode("utf-8"))

        # since yapf>=0.3: 0 unchanged, 2 changed
        if popen.returncode not in (0, 2):
            error_lines = (
                stderr.decode("utf-8").strip().replace("\r\n", "\n").split("\n")
            )
            loc, msg = error_lines[-4], error_lines[-1]
            loc = loc[loc.find("line") :]
            raise FormatterError("yapf: {} @ {}".format(msg, loc))

        new_text = stdout.decode("utf-8").replace("\r\n", "\n")

        return new_text


class BlackFormatter(Formatter):
    def format_text(self, text, target):
        cmd = ["black", "-q", "-"]

        popen = self.popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
        )

        stdout, stderr = popen.communicate(text.encode("utf-8"))

        # since yapf>=0.3: 0 unchanged, 2 changed
        if popen.returncode != 0:
            msg = stderr.decode("utf-8").strip()
            raise FormatterError("black: {}".format(msg))

        new_text = stdout.decode("utf-8")

        return new_text


class RustFmtFormatter(Formatter):
    def format_text(self, text, target):
        cmd = [os.path.expanduser("~/.cargo/bin/rustfmt")]

        popen = self.popen(
            cmd,
            cwd=os.path.dirname(target),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )

        stdout, stderr = popen.communicate(text.encode("utf8"))
        if popen.returncode != 0:
            raise FormatterError("rustfmt failed: {}".format(stderr.decode("utf8")))

        new_text = stdout.decode("utf-8").replace("\r\n", "\n")

        return new_text


class ElmFormatFormatter(Formatter):
    def format_text(self, text, target):
        cmd = ["/opt/elm/current/dist_binaries/elm-format", "--stdin"]

        popen = self.popen(
            cmd,
            cwd=os.path.dirname(target),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        )

        stdout, _ = popen.communicate(text.encode("utf8"))
        if popen.returncode != 0:
            raise FormatterError("elm-format failed: {}".format(stdout))

        new_text = stdout.decode("utf-8").replace("\r\n", "\n")

        return new_text


class JavaFormatFormatter(Formatter):
    def format_text(self, text, target):
        cmd = ["/opt/jars/java-format", "-"]

        popen = self.popen(
            cmd,
            cwd=os.path.dirname(target),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        )

        stdout, _ = popen.communicate(text.encode("utf8"))
        if popen.returncode != 0:
            raise FormatterError("java-format failed: {}".format(stdout))

        new_text = stdout.decode("utf-8").replace("\r\n", "\n")

        return new_text


class TidyFormatter(Formatter):
    def format_text(self, text, target):
        cmd = [
            "tidy",
            "-utf8",
            "-q",
            "--clean",
            "no",
            "--indent",
            "yes",
            "--indent-spaces",
            "2",
            "--indent-with-tabs",
            "no",
            "--drop-empty-elements",
            "no",
            "--drop-empty-paras",
            "no",
            "--tidy-mark",
            "no",
        ]

        popen = self.popen(
            cmd,
            cwd=os.path.dirname(target),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
        )

        stdout, stderr = popen.communicate(text.encode("utf8"))

        if stderr:
            print("tidy (status: {}) warnings: {}".format(popen.returncode, stderr))

        # 0: all good, 1: warnigs, 2: errors
        if popen.returncode not in (0, 1):
            raise FormatterError("tidy failed: {}".format(stdout))

        # for some reason, tidy adds trailing whitespace after <script>-tags
        new_text = "".join(
            line.rstrip() + "\n" for line in stdout.decode("utf-8").splitlines()
        )

        return new_text


class ClangFormatFormatter(Formatter):
    def format_text(self, text, target):
        cmd = ["/usr/bin/clang-format-3.8", "--style=Mozilla"]

        popen = self.popen(
            cmd,
            cwd=os.path.dirname(target),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        )

        stdout, _ = popen.communicate(text.encode("utf8"))
        if popen.returncode != 0:
            raise FormatterError("clang-format failed: {}".format(stdout))

        new_text = stdout.decode("utf-8").replace("\r\n", "\n")

        return new_text


class NoopFormatter(Formatter):
    def format_text(self, text, target):
        print("Not reformatting, cannot find appropriate formatter")
        return text


class EventListener(sublime_plugin.EventListener):
    def on_pre_save(self, view):
        enabled = view.settings().get(CONFIGURATION_KEY)
        # FIXME: Use a global settings to file to set the default.
        if enabled is None:
            enabled = True

        if enabled:
            view.run_command("auto_yapf")
        else:
            print(
                'Not running AutoYapf, as it is disabled through the "{}"setting'.format(
                    CONFIGURATION_KEY
                )
            )


class AutoYapfCommand(sublime_plugin.TextCommand):
    def guess_lang(self):
        if self.view.score_selector(0, "source.java") > 0:
            return "java"
        if self.view.score_selector(0, "source.python") > 0:
            return "python"
        if self.view.score_selector(0, "source.rust") > 0:
            return "rust"
        # if self.view.score_selector(0, 'text.html') > 0:
        #    return 'html'
        if self.view.score_selector(0, "source.c++") > 0:
            return "c++"
        if self.view.score_selector(0, "source.elm") > 0:
            return "elm"

    def is_enabled(self):
        return self.guess_lang() is not None

    def run(self, edit):
        fn = self.view.file_name()

        # determine current text
        selection = sublime.Region(0, self.view.size())
        guess = self.guess_lang()
        print("AutoYapf language: {}".format(guess))

        formatter = {
            "java": JavaFormatFormatter,
            "python": BlackFormatter,
            "rust": RustFmtFormatter,
            "html": TidyFormatter,
            "c++": ClangFormatFormatter,
            "elm": ElmFormatFormatter,
            None: NoopFormatter,
        }[self.guess_lang()]()

        current_text = self.view.substr(selection)
        try:
            new_text = formatter.format_text(current_text, fn)
        except FormatterError as e:
            print("AutoYapf: Formatter failed: {}".format(e))
            sublime.status_message(str(e))
        else:
            self.view.replace(edit, selection, new_text)
