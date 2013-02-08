import sublime
import sublime_plugin
import os.path
import subprocess
import re
import time


class TortoiseError(Exception):
    pass


class NotFoundError(TortoiseError):
    pass


class RepositoryNotFoundError(NotFoundError):
    pass


file_status_cache = {}


class TortoiseCommand():
    def get_path(self, paths):
        if paths == True:
            return self.window.active_view().file_name()
        return paths[0] if paths else self.window.active_view().file_name()

    def get_vcs(self, path):
        if path == None:
            raise TortoiseError('Unable to run commands on an unsaved file.')
        vcs = None

        try:
            vcs = TortoiseSVN(Info.get('svn_tortoiseproc_path'), path)
        except (RepositoryNotFoundError):
            pass

        try:
            vcs = TortoiseGit(Info.get('git_tortoiseproc_path'), path)
        except (RepositoryNotFoundError):
            pass

        try:
            vcs = TortoiseHg(Info.get('hg_hgtk_path'), path)
        except (RepositoryNotFoundError):
            pass

        if vcs == None:
            raise TortoiseError(
                'The current file does not appear to be ' +
                'in a SVN, Git or Mercurial working copy.')

        return vcs

    def menus_enabled(self):
        return Info.get('enable_menus', True)


def handles_error(fn):
    def handler(self, *args, **kwargs):
        try:
            fn(self, *args, **kwargs)
        except (TortoiseError) as (exception):
            sublime.error_message('Tortoise: ' + str(exception))
    return handler


def invisible_when_error(fn):
    def handler(self, *args, **kwargs):
        try:
            res = fn(self, *args, **kwargs)
            if res != None:
                return res
            return True
        except (TortoiseError):
            return False
    return handler


class TortoiseExploreCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).explore(path if paths else None)


class TortoiseCommitCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).commit(path if os.path.isdir(path) else None)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseStatusCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).status(path if os.path.isdir(path) else None)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseSyncCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).sync(path if os.path.isdir(path) else None)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseLogCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).log(path if paths else None)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        vcs = self.get_vcs(path)
        if os.path.isdir(path):
            return True
        return path and vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_error
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return path and self.get_vcs(path).get_status(path) in \
            ['', 'M', 'R', 'C', 'U']

class TortoiseBlameCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).blame(path if paths else None)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if os.path.isdir(path):
            return False
        vcs = self.get_vcs(path)
        return path and vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_error
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return False
        return path and self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

class TortoiseDiffCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).diff(path if paths else None)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        vcs = self.get_vcs(path)
        if os.path.isdir(path):
            return True
        return vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_error
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        vcs = self.get_vcs(path)
        if isinstance(vcs, TortoiseHg):
            return vcs.get_status(path) in ['M']
        else:
            return vcs.get_status(path) in ['A', 'M', 'R', 'C', 'U']


class TortoiseAddCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).add(path)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in ['D', '?']


class TortoiseRemoveCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).remove(path)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_error
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return self.get_vcs(path).get_status(path) in ['']


class TortoiseRevertCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_error
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).revert(path)

    @invisible_when_error
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_error
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return self.get_vcs(path).get_status(path) in \
            ['A', 'M', 'R', 'C', 'U']


class TortoiseBase():
    def get_status(self, path):
        global file_status_cache
        status = ''

        if path in file_status_cache:
            if file_status_cache[path]['time'] > time.time():
                if Info.get('debug'):
                    print 'Fetching cached status for %s' % path
                return file_status_cache[path]['status']

        if Info.get('debug'):
            start_time = time.time()

        try:
            status = self.new_vcs().check_status(path)
        except (Exception) as (exception):
            sublime.error_message(str(exception))

        file_status_cache[path] = {
            'time': time.time() + Info.get('cache_length'),
            'status': status
        }

        if Info.get('debug'):
            print 'Fetching status for %s in %s seconds' % \
                (path, str(time.time() - start_time))

        return status

    def map_command(self, name):
        mappings = self.get_mappings()
        if name in mappings:
            return mappings[name]
        return name

    def run_command(self, name, path):
        name = self.map_command(name)
        path = self.root_dir if path == None else path
        path = os.path.relpath(path, self.root_dir)
        args = self.get_arguments(name, path)
        Util.run_process(args, self.root_dir)

    def explore(self, path=None):
        path = self.root_dir if path == None else os.path.dirname(path)
        args = 'explorer.exe "%s"' % path
        Util.run_process(args)

    def __getattr__(self, name):
        def handler(*args, **kwargs):
            if name.isalpha():
                self.run_command(name, *args, **kwargs)
        return handler


class TortoiseSVN(TortoiseBase):
    def __init__(self, gui_path, path):
        self.root_dir = Util.find_root('.svn', path, False)
        self.gui_path = gui_path
        if self.gui_path == None:
            self.gui_path = Util.find_binary(
                self.__class__.__name__,
                'TortoiseSVN\\bin\\TortoiseProc.exe',
                'TortoiseProc.exe',
                'svn_tortoiseproc_path')

    def new_vcs(self):
        return SVN(self.root_dir)

    def get_mappings(self):
        return { 'status': 'repostatus', 'sync': 'update' }

    def get_arguments(self, name, path):
        return '"%s" /command:%s /path:"%s"' % (self.gui_path, name, path)


class TortoiseGit(TortoiseBase):
    def __init__(self, gui_path, path):
        self.root_dir = Util.find_root('.git', path)
        self.gui_path = gui_path
        if self.gui_path == None:
            try:
                self.gui_path = Util.find_binary(
                    self.__class__.__name__,
                    'TortoiseGit\\bin\\TortoiseGitProc.exe',
                    'TortoiseGitProc.exe',
                    'git_tortoiseproc_path')
            except (NotFoundError):
                self.gui_path = Util.find_binary(
                    self.__class__.__name__,
                    'TortoiseGit\\bin\\TortoiseProc.exe',
                    'TortoiseGitProc.exe (TortoiseGit >= 1.8.x) or ' +
                    'TortoiseProc.exe (TortoiseGit < 1.8.x)',
                    'git_tortoiseproc_path')

    def new_vcs(self):
        return Git(self.gui_path, self.root_dir)

    def get_mappings(self):
        return { 'status': 'repostatus' }

    def get_arguments(self, name, path):
        return '"%s" /command:%s /path:"%s"' % (self.gui_path, name, path)


class TortoiseHg(TortoiseBase):
    def __init__(self, gui_path, path):
        self.root_dir = Util.find_root('.hg', path)
        self.gui_path = gui_path
        if self.gui_path == None:
            try:
                self.gui_path = Util.find_binary(
                    self.__class__.__name__,
                    'TortoiseHg\\thgw.exe',
                    'thgw.exe',
                    'hg_hgtk_path')
            except (NotFoundError):
                self.gui_path = Util.find_binary(
                    self.__class__.__name__,
                    'TortoiseHg\\hgtk.exe',
                    'thgw.exe (for TortoiseHg v2.x) or ' +
                    'hgtk.exe (for TortoiseHg v1.x)',
                    'hg_hgtk_path')

    def new_vcs(self):
        return Hg(self.gui_path, self.root_dir)

    def get_mappings(self):
        return { 'sync': 'synch', 'diff': 'vdiff' }

    def get_arguments(self, name, path):
        return [self.gui_path, name, '--nofork', path]


class CLI():
    def get_command_output(self, args, strip=True, split=True):
        result = Util.get_process_output([self.cli_path] + args, self.root_dir)
        if strip:
            result = result.strip()
        if split:
            result = result.split('\n')
        return result


class SVN(CLI):
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.cli_path = os.path.join(Info.path, 'svn', 'svn.exe')

    def check_status(self, path):
        output = self.get_command_output(['status', path], strip=False)
        regex = Util.get_path_regex(path, self.root_dir)
        for line in output:
            if len(line) >= 1 and re.search(regex, line) != None:
                return line[0]
        return ''


class Git(CLI):
    def __init__(self, gui_path, root_dir):
        self.root_dir = root_dir
        self.cli_path = Info.get('git_cli_path')
        if self.cli_path == None:
            self.cli_path = os.path.dirname(gui_path) + '\\tgit.exe'
            if not os.path.exists(self.cli_path):
                self.cli_path = Util.find_binary(
                    self.__class__.__name__,
                    'Git\\bin\\git.exe',
                    'git.exe or tgit.exe',
                    'git_cli_path')

    def check_status(self, path):
        if os.path.isdir(path):
            output = self.get_command_output(['log', '-1', path])
            return ('?' if output == [''] else '')
        else:
            output = self.get_command_output(['status', '--short'])
            regex = Util.get_path_regex(path, self.root_dir)
            for line in output:
                if len(line) >= 2 and re.search(regex, line) != None:
                    return line.lstrip()[0].upper()
            return ''


class Hg(CLI):
    def __init__(self, gui_path, root_dir):
        self.root_dir = root_dir
        self.cli_path = os.path.dirname(gui_path) + '\\hg.exe'

    def check_status(self, path):
        if os.path.isdir(path):
            output = self.get_command_output(['log', '-l', '1', '"%s"' % path])
            return ('?' if output == [''] else '')
        else:
            output = self.get_command_output(['status', path], strip=False)
            for line in output:
                if len(line) >= 1:
                    return line[0].upper()
            return ''


class Info:
    name = __name__
    path = os.path.join(sublime.packages_path(), __name__)
    get = sublime.load_settings('%s.sublime-settings' % __name__).get


class Util:
    @staticmethod
    def find_root(name, path, find_first=True):
        result = None
        last_dir = None
        cur_dir  = path if os.path.isdir(path) else os.path.dirname(path)
        while cur_dir != last_dir:
            if result != None:
                if not os.path.exists(os.path.join(cur_dir, name)):
                    break
            if os.path.exists(os.path.join(cur_dir, name)):
                result = cur_dir
                if find_first:
                    break
            last_dir = cur_dir
            cur_dir  = os.path.dirname(cur_dir)

        if result == None:
            raise RepositoryNotFoundError(
                'Unable to find "' + name + '" directory.')
        return result

    @staticmethod
    def find_path(path_suffix):
        result = None
        root_drive = os.path.expandvars('%HOMEDRIVE%\\')
        possible_dirs = ['Program Files\\', 'Program Files (x86)\\']

        for dir in possible_dirs:
            path = root_drive + dir + path_suffix
            if os.path.exists(path):
                result = path
                break

        if result == None:
            raise NotFoundError(
                'Unable to find "' + path_suffix + '".')
        return result

    @staticmethod
    def find_binary(class_name, path_suffix, binary_info, setting_name):
        result = None
        try:
            result = Util.find_path(path_suffix)
        except (NotFoundError):
            root_drive = os.path.expandvars('%HOMEDRIVE%\\')
            normal_path = root_drive + 'Program Files\\' + path_suffix
            raise NotFoundError(
                'Unable to find ' + class_name + ' executable.\n\n' +
                'Please add the path to ' + binary_info + ' to the setting ' +
                '"' + setting_name + '" in "' + sublime.packages_path() +
                '\\Tortoise\\Tortoise.sublime-settings".\n\nExample:\n\n' +
                '{"' + setting_name + '": r"' + normal_path + '"}')
        return result

    @staticmethod
    def get_path_regex(path, root):
        result = re.escape(path.replace(root + '\\', '', 1)) + '$'
        for s in ['\/', '\\\\']:
            result = result.replace(s, '[\\/\\\\]')
        return result

    @staticmethod
    def run_process(args, path=None, startupinfo=None):
        return subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            cwd=path)

    @staticmethod
    def get_process_output(args, path=None):
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            startupinfo = None

        proc = Util.run_process(args, path, startupinfo)

        return proc.stdout.read().replace('\r\n', '\n').rstrip(' \n\r')
