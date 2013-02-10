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
    TYPE_ANY = 0
    TYPE_DIR = 1
    TYPE_FILE = 2
    TYPE_VAR = 3

    def get_path(self, paths):
        if paths == True or not paths:
            return self.window.active_view().file_name()
        return paths[0]

    def get_vcs(self, path):
        result = None

        if path == None:
            raise TortoiseError('Unable to run commands on an unsaved file.')

        for create_vcs_func in [
            lambda: TortoiseHg(Info.get('hg_hgtk_path'), path),
            lambda: TortoiseGit(Info.get('git_tortoiseproc_path'), path),
            lambda: TortoiseSVN(Info.get('svn_tortoiseproc_path'), path)
        ]:
            try:
                result = create_vcs_func()
                break
            except (RepositoryNotFoundError):
                pass

        if result == None:
            raise TortoiseError(
                'The current file does not appear to be ' +
                'in a Mercurial, Git or SVN working copy.')

        return result

    def run(self, paths=None):
        path = self.get_path(paths)
        if self.command_type == TortoiseCommand.TYPE_VAR:
            args = path
        elif self.command_type == TortoiseCommand.TYPE_DIR:
            args = path if os.path.isdir(path) else None
        else:
            args = path if paths else None
        try:
            getattr(self.get_vcs(path), self.command_name)(args)
        except (TortoiseError) as (exception):
            sublime.error_message('Tortoise: ' + str(exception))

    def is_visible(self, paths=None):
        if not Info.get('enable_menus', True):
            return False
        path = self.get_path(paths)
        if path:
            try:
                vcs = self.get_vcs(path) # is path managed by VCS?
                if self.command_type != TortoiseCommand.TYPE_VAR:
                    if os.path.isdir(path):
                        return self.command_type != TortoiseCommand.TYPE_FILE
                if self.has_list('visible'):
                    return vcs.get_status(path) in self.get_list('visible', vcs)
            except (TortoiseError):
                pass
        return False

    def is_enabled(self, paths=None):
        path = self.get_path(paths)
        if path:
            if os.path.isdir(path):
                return self.command_type != TortoiseCommand.TYPE_FILE
            try:
                if self.has_list('enabled'):
                    vcs = self.get_vcs(path)
                    return vcs.get_status(path) in self.get_list('enabled', vcs)
                return True
            except (TortoiseError):
                pass
        return False

    def description(self, **args):
        name = 'Tortoise'
        if Info.get('show_vcs_name') and 'paths' in args:
            try:
                path = self.get_path(args['paths'])
                name = self.get_vcs(path).__class__.__name__
            except (TortoiseError):
                pass
        return name + ' ' + self.command_name.title() + '...'

    def has_list(self, name):
        return hasattr(self, 'get_%s_list' % name) or \
              (hasattr(self, name + '_list') and getattr(self, name + '_list'))

    def get_list(self, name, vcs):
        if hasattr(self, 'get_%s_list' % name):
            return getattr(self, 'get_%s_list' % name)(vcs)
        if hasattr(self, name + '_list'):
            return getattr(self, name + '_list')
        return None


class TortoiseExploreCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'explore'
    command_type = TortoiseCommand.TYPE_ANY


class TortoiseCommitCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'commit'
    command_type = TortoiseCommand.TYPE_DIR


class TortoiseStatusCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'status'
    command_type = TortoiseCommand.TYPE_DIR


class TortoiseSyncCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'sync'
    command_type = TortoiseCommand.TYPE_DIR


class TortoiseLogCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'log'
    command_type = TortoiseCommand.TYPE_ANY
    visible_list = ['A', '', 'M', 'R', 'C', 'U']
    enabled_list = ['', 'M', 'R', 'C', 'U']


class TortoiseBlameCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'blame'
    command_type = TortoiseCommand.TYPE_FILE
    visible_list = ['A', '', 'M', 'R', 'C', 'U']
    enabled_list = ['A', '', 'M', 'R', 'C', 'U']


class TortoiseDiffCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'diff'
    command_type = TortoiseCommand.TYPE_ANY
    visible_list = ['A', '', 'M', 'R', 'C', 'U']
    enabled_list = True

    def get_enabled_list(self, vcs):
        if isinstance(vcs, TortoiseHg):
            return ['M']
        return ['A', 'M', 'R', 'C', 'U']


class TortoiseAddCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'add'
    command_type = TortoiseCommand.TYPE_VAR
    visible_list = ['D', '?']
    enabled_list = False


class TortoiseRemoveCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'remove'
    command_type = TortoiseCommand.TYPE_VAR
    visible_list = ['A', '', 'M', 'R', 'C', 'U']
    enabled_list = ['']


class TortoiseRevertCommand(TortoiseCommand, sublime_plugin.WindowCommand):
    command_name = 'revert'
    command_type = TortoiseCommand.TYPE_VAR
    visible_list = ['A', '', 'M', 'R', 'C', 'U']
    enabled_list = ['A', 'M', 'R', 'C', 'U']


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
