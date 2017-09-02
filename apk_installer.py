import sublime
import sublime_plugin
import subprocess
import re
import os
import os.path
import telnetlib
from fnmatch import fnmatch
from datetime import datetime

apk_options = [
	'Install Directly',
	'Uninstall Existing',
	'Uninstall Existing Then Install',
	'Clear Data',
	'Clear Data Then Install'
]

apk_views = []

def get_apk_view(view):
	return next((v for v in apk_views if v.view.id() == view.id()), None)

def decode(ind):
	try:
		return ind.decode("utf-8")
	except:
		try:
			return ind.decode(sys.getdefaultencoding())
		except:
			return ind

def get_settings_value(settings, key, default):
	if settings.has(key):
		return settings.get(key)
	else:
		settings = sublime.load_settings('ApkInstaller.sublime-settings')
		if settings.has(key):
			return settings.get(key)
	return default

def executeCmd(cmd):
	try:
		print('executing %s' % cmd)
		settings = sublime.active_window().active_view().settings()
		setting_value = get_settings_value(settings, cmd[0], cmd[0])
		if setting_value != cmd[0]:
			print(setting_value)
			cmd[0] = setting_value
		proc = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		out, err = proc.communicate()
		out = decode(out)
		err = decode(err)
		return (proc.returncode == 0, out + '\n' + err)
	except Exception as e:
		sublime.error_message("Error trying to exec cmd: %s" % (cmd))
		return (False, "")

def log(view, data):
	data = data.strip()
	if len(data) > 0:
		data = data.replace('\r', '') + '\n'
		view.run_command('content', {'data': data})

class ApkView(object):
	def __init__(self, apk_path, badging):
		super(ApkView, self).__init__()
		self.apk_path = apk_path
		self.view = sublime.active_window().new_file()
		self.view.set_name('[%s]' % os.path.basename(apk_path))
		self.view.set_read_only(True)
		self.view.set_scratch(True)
		self.error = True
		self.last_apk_command = None
		self.last_selected_device = None
		self.generateApkInfo(badging.replace('\r', ''))
		self.view.set_syntax_file('Packages/YAML/YAML.sublime-syntax')
		if not self.error:
			self.view.show_popup_menu(apk_options, self.on_selected_apk_options)
		# self.view.window().show_quick_panel(apk_options, self.on_selected_apk_options)

	def on_selected_apk_options(self, selected):
		if selected == -1:
			return
		if selected == 0:
			self.last_apk_command = 'install_apk'
		elif selected == 1:
			self.last_apk_command = 'uninstall_apk'
		elif selected == 2:
			self.last_apk_command = 'uninstall_then_install_apk'
		elif selected == 3:
			self.last_apk_command = 'clear_data'
		elif selected == 4:
			self.last_apk_command = 'clear_data_then_install_apk'
		self.try_run_cmd(self.last_apk_command)

	def try_run_cmd(self, text_cmd):
		if self.error:
			return
		devices, options = getDevices()
		if len(devices) == 1:
			self.last_selected_device = devices[0]
			self.run_command(text_cmd)
		elif len(devices) > 1:
			self.last_apk_command = text_cmd
			self.view.show_popup_menu(options, self.on_selected_device)
			# sublime.active_window().show_quick_panel(options, on_selected_device)

	def run_command(self, cmd):
		if cmd == 'install_apk':
			self._installApk()
		elif cmd == 'uninstall_apk':
			self._uninstallPackage()
		elif cmd == 'uninstall_then_install_apk':
			self._uninstallPackage()
			self._installApk()
		elif cmd == 'clear_data':
			self._clearData()
		elif cmd == 'clear_data_then_install_apk':
			self._clearData()
			self._installApk()

	def _installApk(self):
		log(self.view, "Installing: %s on %s" % (self.apk_path, self.last_selected_device))
		success, out = executeCmd(['adb', '-s', self.last_selected_device, 'install', '-r', '-d', self.apk_path])
		if not success:
			log(self.view, out)
			return
		log(self.view, out + "Installed: %s" % self.apk_path)

	def _uninstallPackage(self):
		log(self.view, "Uninstalling: %s on %s" % (self.package, self.last_selected_device))
		success, out = executeCmd(['adb', '-s', self.last_selected_device, 'shell', 'pm', 'uninstall', self.package])
		if not success:
			log(self.view, out)
			return
		log(self.view, out + '\n' + "Uninstalled: %s" % self.package)

	def _clearData(self):
		log(self.view, "Clearing data: %s on %s" % (self.package, self.last_selected_device))
		success, out = executeCmd(['adb', '-s', self.last_selected_device, 'shell', 'pm', 'clear', self.package])
		if not success:
			log(self.view, out)
			return
		log(self.view, out + '\n' + "Cleared data: %s" % self.package)


	def on_selected_device(self, selected):
		self.last_selected_device = last_devices[selected]
		self.run_command(self.last_apk_command)

	def sizeof_fmt(self, num, suffix='B'):
		for unit in ['','K','M','G','T','P','E','Z']:
			if abs(num) < 1024.0:
				return "%3.1f%s%s" % (num, unit, suffix)
			num /= 1024.0
		return "%.1f%s%s" % (num, 'Yi', suffix)

	def generateApkInfo(self, badging):
		badging = badging.replace('\r', '')
		lines = list(filter(lambda l: len(l), badging.split('\n')))
		kvLines = list(map(lambda kv: list(map(lambda e: e.strip(' \''), kv)),
			list(filter(lambda l: len(l) == 2,
				list(map(lambda l: l.split(':'), lines))))))
		packageInfo = next((kv for kv in kvLines if kv[0] == 'package'), None)
		targetSdk = next((kv for kv in kvLines if kv[0] == 'targetSdkVersion'), None)
		appName = next((kv for kv in kvLines if kv[0] == 'application-label'), None)
		nativeCode = next((kv for kv in kvLines if kv[0] == 'native-code'), None)
		sdkVersion = next((kv for kv in kvLines if kv[0] == 'sdkVersion'), None)
		view_content = 'Failed to get apk badging'
		if packageInfo:
			info = packageInfo[1].split(' ')
			packageInfo = {}
			for x in info:
				x = x.split('=')
				packageInfo[x[0]] = x[1].strip('\'')
		else:
			print(badging)
			self.view.run_command("content", {"data": view_content})
			return
		if targetSdk and appName and nativeCode and sdkVersion:
			self.package = packageInfo['name']
			self.label = appName[1]
			self.version_name = packageInfo['versionName']
			self.version_code = packageInfo['versionCode']
			self.min_sdk_version = sdkVersion[1]
			self.target_sdk_version = targetSdk[1]
			self.native_code = nativeCode[1].replace('\'', '')
			self.file_size = self.sizeof_fmt(os.stat(self.apk_path).st_size)
		else:
			print(badging)
			self.view.run_command("content", {"data": view_content})
			return

		view_content = ("package: %s\n" % self.package) +\
				("application label: %s\n" % self.label) +\
				("version name: %s\n" % self.version_name) +\
				("version code: %s\n" % self.version_code) +\
				("\nmin sdk version: %s\n" % self.min_sdk_version) +\
				("target sdk version: %s\n" % self.target_sdk_version) +\
				("native code: %s\n" % self.native_code) +\
				("file path: %s\n" % self.apk_path) +\
				("file size: %s\n" % self.file_size) +\
				"\n----------------------------------\n\n"
		self.error = False
		self.view.run_command("content", {"data": view_content})



def openApkFile(path):
	success, badging = executeCmd(['aapt', 'd', 'badging', path])
	if not success:
		return
	apk_views.append(ApkView(path, badging))

def getDevices():
	success, out = executeCmd(['adb', 'devices'])
	if not success:
		sublime.error_message('Failed to get attached devices\n' + out)
		return
	devices = []
	for line in out.split("\n"):
		line = line.strip()
		if line.endswith("device"):
			devices.append(re.sub(r"[ \t]*device$", "", line))
	options = []
	for device in devices:
		# dump build.prop
		success, build_prop = executeCmd(['adb', "-s", device, "shell", "cat /system/build.prop"])
		# get name
		product = "Unknown"  # should never actually see this
		if device.startswith("emulator"):
			port = int(device.rsplit("-")[-1])
			t = telnetlib.Telnet("localhost", port)
			t.read_until(b"OK", 1000)
			t.write(b"avd name\n")
			product = t.read_until(b"OK", 1000).decode("utf-8")
			t.close()
			product = product.replace("OK", "").strip()
		else:
			product = re.findall(r"^ro\.product\.model=(.*)$", build_prop, re.MULTILINE)
			if product:
				product = product[0]
		# get version
		version = re.findall(r"ro\.build\.version\.release=(.*)$", build_prop, re.MULTILINE)
		if version:
			version = version[0]
		else:
			version = "Android"
		product = str(product).strip()
		version = str(version).strip()
		device = str(device).strip()
		options.append("%s %s - %s" % (product, version, device))

	if len(options) == 0:
		sublime.error_message("No device attached!")
		return
	global last_devices
	last_devices = devices
	return (devices, options)

class ContentCommand(sublime_plugin.TextCommand):
	def run(self, e, data):
		self.view.set_read_only(False)
		self.view.insert(e, self.view.size(), data)
		self.view.set_read_only(True)

class ApkInstallerListener(sublime_plugin.EventListener):
	def on_activated(self, view):
		self.processApk(view)

	def processApk(self, view):
		path = view.file_name()
		if path and (fnmatch(path, "*.apk") or fnmatch(path, "*.APK")):
			view.close()
			openApkFile(path)

def try_run_cmd_for_view(view, cmd):
	apk_view = get_apk_view(view)
	if apk_view:
		apk_view.try_run_cmd(cmd)

class InstallApkWrapperCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		try_run_cmd_for_view(self.view, 'install_apk')

class UninstallApkWrapperCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		try_run_cmd_for_view(self.view, 'uninstall_apk')

class UninstallThenInstallApkWrapperCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		try_run_cmd_for_view(self.view, 'uninstall_then_install_apk')

class ClearDataWrapperCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		try_run_cmd_for_view(self.view, 'clear_data')

class ClearDataThenInstallApkWrapperCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		try_run_cmd_for_view(self.view, 'clear_data_then_install_apk')
