import sublime
import sublime_plugin
import os.path
import subprocess
import re
import time


class RepositoryNotFoundError(Exception):
    pass


class NotFoundError(Exception):
    pass


file_status_cache = {}


class TortoiseCommand():
    def get_path(self, paths):
        if paths == True:
            return self.window.active_view().file_name()
        return paths[0] if paths else self.window.active_view().file_name()

    def get_vcs(self, path):
        settings = sublime.load_settings('Tortoise.sublime-settings')

        if path == None:
            raise NotFoundError('Unable to run commands on an unsaved file')
        vcs = None

        try:
            vcs = TortoiseSVN(settings.get('svn_tortoiseproc_path'), path)
        except (RepositoryNotFoundError):
            pass

        try:
            vcs = TortoiseGit(settings.get('git_tortoiseproc_path'), path)
        except (RepositoryNotFoundError):
            pass

        try:
            vcs = TortoiseHg(settings.get('hg_hgtk_path'), path)
        except (RepositoryNotFoundError):
            pass

        if vcs == None:
            raise NotFoundError(
                'The current file does not appear to be ' +
                'in a SVN, Git or Mercurial working copy.')

        return vcs

    def menus_enabled(self):
        settings = sublime.load_settings('Tortoise.sublime-settings')
        return settings.get('enable_menus', True)


def handles_not_found(fn):
    def handler(self, *args, **kwargs):
        try:
            fn(self, *args, **kwargs)
        except (NotFoundError) as (exception):
            sublime.error_message('Tortoise: ' + str(exception))
    return handler


def invisible_when_not_found(fn):
    def handler(self, *args, **kwargs):
        try:
            res = fn(self, *args, **kwargs)
            if res != None:
                return res
            return True
        except (NotFoundError):
            return False
    return handler


class TortoiseExploreCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).explore(path if paths else None)


class TortoiseCommitCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).commit(path if os.path.isdir(path) else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseStatusCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).status(path if os.path.isdir(path) else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseSyncCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).sync(path if os.path.isdir(path) else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if not path:
            return False
        self.get_vcs(path)
        return os.path.isdir(path)


class TortoiseLogCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).log(path if paths else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        vcs = self.get_vcs(path)
        if os.path.isdir(path):
            return True
        return path and vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return path and self.get_vcs(path).get_status(path) in \
            ['', 'M', 'R', 'C', 'U']

class TortoiseBlameCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).blame(path if paths else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        if os.path.isdir(path):
            return False
        vcs = self.get_vcs(path)
        return path and vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return False
        return path and self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

class TortoiseDiffCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).diff(path if paths else None)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        vcs = self.get_vcs(path)
        if os.path.isdir(path):
            return True
        return vcs.get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
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
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).add(path)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in ['D', '?']


class TortoiseRemoveCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).remove(path)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return self.get_vcs(path).get_status(path) in ['']


class TortoiseRevertCommand(sublime_plugin.WindowCommand, TortoiseCommand):
    @handles_not_found
    def run(self, paths=None):
        path = self.get_path(paths)
        self.get_vcs(path).revert(path)

    @invisible_when_not_found
    def is_visible(self, paths=None):
        if not self.menus_enabled():
            return False
        path = self.get_path(paths)
        return self.get_vcs(path).get_status(path) in \
            ['A', '', 'M', 'R', 'C', 'U']

    @invisible_when_not_found
    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if os.path.isdir(path):
            return True
        return self.get_vcs(path).get_status(path) in \
            ['A', 'M', 'R', 'C', 'U']


class ForkGui():
    def __init__(self, cmd, cwd):
        subprocess.Popen(cmd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=cwd)


class TortoiseBase():
    def get_status(self, path):
        global file_status_cache
        status = ''
        settings = sublime.load_settings('Tortoise.sublime-settings')

        if path in file_status_cache:
            if file_status_cache[path]['time'] > time.time():
                if settings.get('debug'):
                    print 'Fetching cached status for %s' % path
                return file_status_cache[path]['status']

        if settings.get('debug'):
            start_time = time.time()

        try:
            status = self.new_vcs().check_status(path)
        except (Exception) as (exception):
            sublime.error_message(str(exception))

        file_status_cache[path] = {
            'time': time.time() + settings.get('cache_length'),
            'status': status
        }

        if settings.get('debug'):
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
        ForkGui(args, self.root_dir)

    def explore(self, path=None):
        path = self.root_dir if path == None else os.path.dirname(path)
        args = 'explorer.exe "%s"' % path
        ForkGui(args, None)

    def status(self, path=None):
        self.run_command('status', path)

    def commit(self, path=None):
        self.run_command('commit', path)

    def sync(self, path=None):
        self.run_command('sync', path)

    def log(self, path=None):
        self.run_command('log', path)

    def blame(self, path=None):
        self.run_command('blame', path)

    def diff(self, path):
        self.run_command('diff', path)

    def add(self, path):
        self.run_command('add', path)

    def remove(self, path):
        self.run_command('remove', path)

    def revert(self, path):
        self.run_command('revert', path)


class TortoiseSVN(TortoiseBase):
    def __init__(self, binary_path, file):
        self.root_dir = Util.find_root('.svn', file, False)
        if binary_path != None:
            self.path = binary_path
        else:
            self.path = Util.find_binary(
                self.__class__.__name__,
                'TortoiseSVN\\bin\\TortoiseProc.exe',
                'TortoiseProc.exe',
                'svn_tortoiseproc_path')

    def new_vcs(self):
        return SVN(self.root_dir)

    def get_mappings(self):
        return {
            'status': 'repostatus',
            'sync': 'update'
        }

    def get_arguments(self, name, path):
        return '"%s" /command:%s /path:"%s"' % (self.path, name, path)


class TortoiseGit(TortoiseBase):
    def __init__(self, binary_path, file):
        self.root_dir = Util.find_root('.git', file)
        if binary_path != None:
            self.path = binary_path
        else:
            self.path = Util.find_binary(
                self.__class__.__name__,
                'TortoiseGit\\bin\\TortoiseProc.exe',
                'TortoiseProc.exe',
                'git_tortoiseproc_path')

    def new_vcs(self):
        return Git(self.path, self.root_dir)

    def get_mappings(self):
        return {
            'status': 'repostatus'
        }

    def get_arguments(self, name, path):
        return '"%s" /command:%s /path:"%s"' % (self.path, name, path)


class TortoiseHg(TortoiseBase):
    def __init__(self, binary_path, file):
        self.root_dir = Util.find_root('.hg', file)
        if binary_path != None:
            self.path = binary_path
        else:
            try:
                self.path = Util.find_binary(
                    self.__class__.__name__,
                    'TortoiseHg\\thgw.exe',
                    'thgw.exe',
                    'hg_hgtk_path')
            except (NotFoundError):
                self.path = Util.find_binary(
                    self.__class__.__name__,
                    'TortoiseHg\\hgtk.exe',
                    'thgw.exe (for TortoiseHg v2.x) or ' +
                    'hgtk.exe (for TortoiseHg v1.x)',
                    'hg_hgtk_path')

    def new_vcs(self):
        return Hg(self.path, self.root_dir)

    def get_mappings(self):
        return {
            'sync': 'synch',
            'diff': 'vdiff'
        }

    def get_arguments(self, name, path):
        return [self.path, name, '--nofork', path]


class NonInteractiveProcess():
    def __init__(self, args, cwd=None):
        self.args = args
        self.cwd  = cwd

    def run(self):
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.Popen(
            self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            startupinfo=startupinfo,
            cwd=self.cwd)

        return proc.stdout.read().replace('\r\n', '\n').rstrip(' \n\r')


class VCS():
    def run_niprocess(self, args):
        return NonInteractiveProcess(args, cwd=self.root_dir).run()


class SVN(VCS):
    def __init__(self, root_dir):
        self.root_dir = root_dir

    def check_status(self, path):
        stp_path = sublime.packages_path()
        svn_path = os.path.join(stp_path, __name__, 'svn', 'svn.exe')
        args = [svn_path, 'status', path]
        result = self.run_niprocess(args).split('\n')
        for line in result:
            if len(line) < 1:
                continue

            path_without_root = path.replace(self.root_dir + '\\', '', 1)
            path_regex = re.escape(path_without_root) + '$'
            if self.root_dir != path and re.search(path_regex, line) == None:
                continue

            return line[0]
        return ''


class Git(VCS):
    def __init__(self, tortoise_proc_path, root_dir):
        settings = sublime.load_settings('Tortoise.sublime-settings')
        self.root_dir = root_dir
        self.git_path = settings.get('git_exe_path')
        if self.git_path == None:
            self.git_path = os.path.dirname(tortoise_proc_path) + '\\tgit.exe'
            if not os.path.exists(self.git_path):
                self.git_path = Util.find_binary(
                    self.__class__.__name__,
                    'Git\\bin\\git.exe',
                    'git.exe or tgit.exe',
                    'git_exe_path')

    def check_status(self, path):
        if os.path.isdir(path):
            return self.check_status_dir(path)
        else:
            return self.check_status_file(path)

    def check_status_dir(self, path):
        args = [self.git_path, 'log', '-1', path]
        result = self.run_niprocess(args).strip().split('\n')
        return ('?' if result == [''] else '')

    def check_status_file(self, path):
        args = [self.git_path, 'status', '--short']
        result = self.run_niprocess(args).strip().split('\n')
        for line in result:
            if len(line) < 2:
                continue
            path_without_root = path.replace(self.root_dir + '\\', '', 1)
            path_regex = re.escape(path_without_root) + '$'
            if self.root_dir != path and re.search(path_regex, line) == None:
                continue

            return (line[0] if line[0] != ' ' else line[1]).upper()
        return ''


class Hg(VCS):
    def __init__(self, tortoise_proc_path, root_dir):
        self.root_dir = root_dir
        self.hg_path = os.path.dirname(tortoise_proc_path) + '\\hg.exe'

    def check_status(self, path):
        if os.path.isdir(path):
            return self.check_status_dir(path)
        else:
            return self.check_status_file(path)

    def check_status_dir(self, path):
        args = [self.hg_path, 'log', '-l', '1', '"' + path + '"']
        result = self.run_niprocess(args).strip().split('\n')
        return ('?' if result == [''] else '')

    def check_status_file(self, path):
        args = [self.hg_path, 'status', path]
        result = self.run_niprocess(args).split('\n')
        for line in result:
            if len(line) < 1:
                continue
            return line[0].upper()
        return ''


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