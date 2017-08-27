import sublime
import sublime_plugin
import subprocess
import os
from fnmatch import fnmatch

apk_options = [
    'Install Directly',
    'Uninstall Existing',
    'Uninstall Existing Then Install',
    'Clear Data',
    'Clear Data Then Install'
]
global last_package
global last_apk_path

def decode(ind):
    try:
        return ind.decode("utf-8")
    except:
        try:
            return ind.decode(sys.getdefaultencoding())
        except:
            return ind

def executeCmd(cmd):
    try:
        print('executing %s' % cmd)
        proc = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE)
        out, err = proc.communicate()
        return decode(out)
    except Exception as e:
        sublime.error_message("Error trying to exec cmd: %s" % (cmd))
        return ""

def sizeof_fmt(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def generateApkInfo(apkInfo, path):
    apkInfo = apkInfo.replace('\r', '')
    lines = list(filter(lambda l: len(l), apkInfo.split('\n')))
    kvLines = list(map(lambda kv: list(map(lambda e: e.strip(' \''), kv)),
        list(filter(lambda l: len(l) == 2,
            list(map(lambda l: l.split(':'), lines))))))
    packageInfo = next((kv for kv in kvLines if kv[0] == 'package'), None)
    targetSdk = next((kv for kv in kvLines if kv[0] == 'targetSdkVersion'), None)
    appName = next((kv for kv in kvLines if kv[0] == 'application-label'), None)
    nativeCode = next((kv for kv in kvLines if kv[0] == 'native-code'), None)
    if packageInfo:
        info = packageInfo[1].split(' ')
        packageInfo = {}
        for x in info:
            x = x.split('=')
            packageInfo[x[0]] = x[1].strip('\'')
    global last_package
    last_package = packageInfo['name']
    global last_apk_path
    last_apk_path = path
    print("last pkg: %s\nlast apk: %s" % (last_package, last_apk_path))
    return ("package: %s\n" % packageInfo['name']) +\
            ("application label: %s\n" % appName[1]) +\
            ("version name: %s\n" % packageInfo['versionName']) +\
            ("version code: %s\n" % packageInfo['versionCode']) +\
            ("\ntarget sdk version: %s\n" % targetSdk[1]) +\
            ("native code: %s\n" % nativeCode[1].replace('\'','')) +\
            ("file path: %s\n" % path) +\
            ("file size: %s\n" % sizeof_fmt(os.stat(path).st_size))

def _installApk(apk):
    sublime.status_message("Installing %s" % apk)
    print(executeCmd(['adb', 'install', '-r', '-d', apk]))
    sublime.status_message("Installed %s" % apk)

def _uninstallPackage(package):
    sublime.status_message("Uninstalling %s" % package)
    print(executeCmd(['adb', 'shell', 'pm', 'uninstall', package]))
    sublime.status_message("Uninstalled %s" % package)

def _clearData(package):
    sublime.status_message("Clearing data: %s" % package)
    print(executeCmd(['adb', 'shell', 'pm', 'clear', package]))
    sublime.status_message("Cleared data: %s" % package)

def on_selected_apk_options(selected):
    if selected == -1:
        return
    global last_apk_path
    global last_package
    if selected == 0:
        _installApk(last_apk_path)
    elif selected == 1:
        _uninstallPackage(last_package)
    elif selected == 2:
        _uninstallPackage(last_package)
        _installApk(last_apk_path)
    elif selected == 3:
        _clearData(last_package)
    elif selected == 4:
        _clearData(last_package)
        _installApk(last_apk_path)

def openApkFile(path):
    apkInfo = executeCmd(['aapt', 'd', 'badging', path])
    apkView = sublime.active_window().new_file()
    apkView.set_name(path)
    apkView.set_scratch(True)
    apkInfo = apkInfo.replace('\r', '')
    apkInfo = generateApkInfo(apkInfo, path)
    apkView.run_command("content", {"data": apkInfo})
    apkView.set_read_only(True)
    apkView.set_syntax_file('Packages/YAML/YAML.sublime-syntax')
    apkView.window().show_quick_panel(apk_options, on_selected_apk_options)


class InstallApkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        devices = executeCmd(['adb', 'devices']).replace('\r', '')
        for line in devices.split('\n'):
            if line.strip().endswith('device'):
                apkView.run_command("example", {"data": [line.strip()]})

class ContentCommand(sublime_plugin.TextCommand):
    def run(self, e, data):
        self.view.insert(e, 0, data)

class InstallApk(sublime_plugin.EventListener):
    def on_activated(self, view):
        path = view.file_name()
        if path and (fnmatch(path, "*.apk") or fnmatch(path, "*.APK")):
            view.close()
            openApkFile(path)
