#!/usr/bin/env python

import os
import sys
import logging
import subprocess
import shutil
import stat
import glob
import re
import tempfile
from combo_runner import action_decorator
from sys import platform as _platform
from combo_runner.base_action_runner import BaseActionRunner
from marionette import Marionette
import mozdevice
from mozlog import structured
from mozdevice.devicemanager import DMError
from gaiatest import GaiaData, GaiaApps, GaiaDevice
from gaiatest.runtests import GaiaTestOptions, GaiaTestRunner
from utils import zip_utils
from utils.device_pool import DevicePool
from flash_tool.utilities.decompressor import Decompressor
from flash_tool.utilities.logger import Logger
from mtbf_driver import mtbf

logger = logging.getLogger("mtbf_operation")
logging.basicConfig(level=logging.DEBUG)

action = action_decorator.action


class MtbfTestOptions(GaiaTestOptions):
    def __init__(self):
        GaiaTestOptions.__init__(self)


class MtbfJobRunner(BaseActionRunner):
    serial = None
    marionette = None
    flash_params = {
        'branch': 'mozilla-b2g34_v2_1-flame-kk-eng',
        'build': '',
        'build_id': ''
    }
    flashed = False

    def __init__(self, **kwargs):
        self.logger = logger
        BaseActionRunner.__init__(self)

    def setup(self):
        if not self.serial or not self.port:
            logger.error("Fail to get device")
            raise DMError
        self.marionette and self.marionette.session and self.marionette.cleanup()
        self.dm = mozdevice.DeviceManagerADB(deviceSerial=self.serial, port=self.port)
        self.marionette = Marionette(device_serial=self.serial, port=self.port)
        self.marionette.start_session()
        self.device = GaiaDevice(marionette=self.marionette, manager=self.dm)
        self.apps = GaiaApps(self.marionette)
        self.data_layer = GaiaData(self.marionette)

    def adb_test(self):
        if not hasattr(self, 'serial') or os.system("ANDROID_SERIAL=" + self.serial + " adb shell ls") != 0:
            logger.error("Device not found or can't be controlled")
            return False
        return True

    @action(enabled=False)
    def add_7mobile_action(self):
        # workaround for waiting for boot
        self.data_layer.set_setting('ril.data.apnSettings',
                                    [[
                                        {"carrier": "(7-Mobile) (MMS)",
                                            "apn": "opentalk",
                                            "mmsc": "http://mms",
                                            "mmsproxy": "210.241.199.199",
                                            "mmsport": "9201",
                                            "types": ["mms"]},
                                        {"carrier": "(7-Mobile) (Internet)",
                                            "apn": "opentalk",
                                            "types": ["default", "supl"]}
                                    ]])
        return True

    @action(enabled=False)
    def change_memory(self):
        #TODO: use native adb/fastboot command to change memory?
        # Make sure it's in fastboot mode, TODO: leverage all fastboot command in one task function
        if self.adb_test():
            os.system("adb reboot bootloader")
            memory = 319
            mem_str = str(memory)
            os.system("fastboot oem mem " + mem_str)
            # Preventing from async timing of fastboot
            os.system("fastboot reboot")
            self.port_forwarding(self.serial, self.port)
            return True
        logger.error("Can't find device")
        self.marionette.wait_for_port()
        self.port_forwarding(self.serial, self.port)
        return False

    @action(enabled=True)
    def collect_memory_report(self):
        zip_utils.collect_about_memory("mtbf_driver")  # TODO: give a correct path for about memory folder

    def get_free_device(self):
        dp = DevicePool(self.serial)
        if dp and dp.get_lock():
            # Record device serial and store dp instance
            self.serial = str(dp)
            self.dp = dp
            if self.is_forwarded(self.serial):
                # device is forwarded before acquired; stop and avoid possible error
                self.serial = None
                raise DMError("Device already in forwarding list")
            os.environ["ANDROID_SERIAL"] = self.serial
            self.port = self.find_available_port()
            if self.port_forwarding(str(dp), self.port):
                return dp
            logger.error("Port forwarding failed")
            raise DMError
        logger.warning("No available device.  Please retry after device released")
        # TODO: more handling for no available device

    def validate_flash_params(self):
        ## Using system environment variable as temporary solution TODO: use other way for input params
        ## Check if package(files)/folder exists and return, else raise exception
        if not 'FLASH_BASEDIR' in os.environ:
            raise AttributeError("No FLASH_BASEDIR set")
        basedir = os.environ['FLASH_BASEDIR']
        if not 'FLASH_BUILDID' in os.environ:
        ## TODO: if latest/ exists, use latest as default
            logging.info("No build id set. search in base dir")
            buildid = ""
            flash_dir = basedir
        else:
            buildid = os.environ['FLASH_BUILDID']
            # re-format build id based on pvt folder structure
            if '-' in buildid:
                buildid = buildid.replace("-", "")
            year = buildid[:4]
            month = buildid[4:6]
            datetime = '-'.join([year, month] + [buildid[i + 6:i + 8] for i in range(0, len(buildid[6:]), 2)])
            flash_dir = os.path.join(basedir, year, month, datetime)
        if not os.path.isdir(flash_dir):
            raise AttributeError("Flash  directory " + flash_dir + " not exist")
        flash_files = glob.glob(os.path.join(flash_dir, '*'))
        flash_src = {}
        for flash_file in flash_files:
            logger.debug("Flash source found: [" + flash_file + "]")
            if os.path.isdir(flash_file):
                continue
            elif "tar.gz" in flash_file:
                flash_src['gecko'] = flash_file
            elif "gaia" in flash_file:
                flash_src['gaia'] = flash_file
            elif "symbol" in flash_file:
                flash_src['symbol'] = flash_file
            elif "zip" in flash_file:
                flash_src['image'] = flash_file
        return flash_src

    @action(enabled=True)
    def full_flash(self):
        flash_src = self.validate_flash_params()
        if self.flashed:
            logger.warning("Flash performed; skip flashing")
            return True
        if not flash_src:
            logger.warning("Invalid build folder/build_id, skip flashing")
            return False
        if not 'image' in flash_src:
            logger.warning("No available image for flash, skip flashing")
            return False
        try:
            self.temp_dir = tempfile.mkdtemp()
            logger.info('Create temporary folder:' + self.temp_dir)
            Decompressor().unzip(flash_src['image'], self.temp_dir)
            # set the permissions to rwxrwxr-x (509 in python's os.chmod)
            os.chmod(self.temp_dir + '/b2g-distro/flash.sh', stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            os.chmod(self.temp_dir + '/b2g-distro/load-config.sh', stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
            os.system('cd ' + self.temp_dir + '/b2g-distro; ./flash.sh -f')
            # support NO_FTU environment for skipping FTU (e.g. monkey test)
            if 'NO_FTU' in os.environ and os.environ['NO_FTU'] == 'true':
                logger.log('The [NO_FTU] is [true].')
                os.system("ANDROID_SERIAL=" + self.serial + 'adb wait-for-device && adb shell stop b2g; (RET=$(adb root); if ! case ${RET} in *"cannot"*) true;; *) false;; esac; then adb remount && sleep 5; else exit 1; fi; ./disable_ftu.py) || (echo "No root permission, cannot setup NO_FTU."); adb reboot;')
        finally:
            try:
                shutil.rmtree(self.temp_dir)  # delete directory
            except OSError:
                logger.error('Can not remove temporary folder:' + self.temp_dir, level=Logger._LEVEL_WARNING)
        self.flashed = True

    @action(enabled=False)
    def shallow_flash(self):
        flash_src = self.validate_flash_params()
        if self.flashed:
            logger.warning("Flash performed; skip flashing")
            return True
        if not flash_src:
            logger.warning("Invalid build folder/build_id, skip flashing")
            return False
        if not 'gaia' in flash_src or not 'gecko' in flash_src:
            logger.warning("No gaia or gecko archive, skip flashing")
            return False
        cmd = 'flash_tool/shallow_flash.sh -y --gecko="' + flash_src['gecko'] + '" --gaia="' + flash_src['gaia'] + '"'
        if _platform == 'darwin':
            cmd = cmd.replace('=', ' ')
        ret = os.system(cmd)
        if ret != 0:
            logger.info("Shallow flash ended abnormally")
            return False
        self.flashed = True
        os.system("ANDROID_SERIAL=" + self.serial + " adb wait-for-device")

    def is_forwarded(self, serial):
        out = subprocess.check_output(['/usr/bin/adb version'], shell=True)
        search = re.search('[0-9\.]+', out)
        os.system("ANDROID_SERIAL=" + self.serial + " adb wait-for-device")
        if search and search.group(0) >= '1.0.31':
            out = subprocess.check_output('/usr/bin/adb forward --list', shell=True)
            search_serial = re.search('\w+', out)
            if search_serial and search_serial.group(0) == serial:
                logger.info("DeviceSerial[" + serial + "] forwarded")
                return int(re.search(' tcp:(\d+) ', out).group(1))
        else:
            logger.info("adb forward --list not supported; recommend to upgrade 1.0.31 or newer version")
        return None

    def port_forwarding(self, serial, port):
        has_port = self.is_forwarded(serial)
        if has_port:
            logger.info("Using existing port [" + str(self.port) + "]")
            self.port = has_port
            return True
        if serial and port:
            ret = os.system("ANDROID_SERIAL=" + serial + " adb forward tcp:" + str(port) + " tcp:2828")
            if ret != 0:
                raise DMError("can't forward port to ANDROID_SERIAL[" + serial + "]")
        logger.info("Port forwarding success serial:[" + serial + "] port:[" + str(port) + "]")
        return True

    def find_available_port(self):
        if 'ANDROID_SERIAL' in os.environ.keys():
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', 0))
            port = sock.getsockname()[1]
            sock.close()
            return port

    @action(enabled=True)
    def enable_certified_apps_debug(self):
        if self.serial:
            os.system("ANDROID_SERIAL=" + self.serial + " flash_tool/enable_certified_apps_for_devtools.sh && adb wait-for-device")
            logger.debug("Successfully enabling certified apps for debugging")
            return True
        return False

    def release(self):
        if hasattr(self, 'dp') and self.dp:
            self.dp.release()
            if self.serial:
                port = self.is_forwarded(self.serial)
                if port:
                # Remove port forwarding
                    os.system("ADNDROID_SERIAL=" + self.serial + " adb forward --remove tcp:" + str(port))
            return True
        else:
            logger.warning("No device allocated")
            return False

    def check_version(self):
        # FIXME: fix check version to use package import
        cmd = "cd flash_tool/ && NO_COLOR=TRUE ./check_versions.py | sed -e 's| \{2,\}||g' -e 's|\[0m||g'"
        if self.serial:
            cmd = "ANDROID_SERIAL=" + self.serial + " " + cmd
        os.system(cmd)

    def mtbf_options(self):
        ## load mtbf parameters
        if not 'MTBF_TIME' in os.environ:
            logger.info("MTBF_TIME is not set, using default value 120.")
            os.environ["MTBF_TIME"] = "120"
        if not 'MTBF_CONF' in os.environ:
            logger.info("MTBF_CONF is not set, using default.conf")
            os.environ["MTBF_CONF"] = "default.conf"

        parser = self.parser.parser
        parser.add_argument("--testvars", help="Test variables for b2g")
        self.parse_options()
        # FIXME: make rootdir of testvars could be customized
        mtbf_testvars_dir = "/mnt/mtbf_shared/testvars"
        if not hasattr(self.options, 'testvars') or not self.options.testvars:
            testvars = os.path.join(mtbf_testvars_dir, "testvars_" + self.serial + ".json")
            if os.path.exists(testvars):
                self.options.testvars = parser.testvars = testvars
                logger.info("testvar [" + testvars + "] found")
            else:
                if os.path.exists(os.path.join(os.getcwd(), "default.json")): 
                    logger.info("using default testvars.json")
                else:
                    raise AttributeError("default testvars doesn't exist")

        ## #TODO: finish parsing arguments for flashing
        ## parser.add_argument("--flashdir", help="directory for pulling build")
        ## parser.add_argument("--buildid", help="build id for pulling build")
        ## self.parse_options()
        ## if hasattr(self.parser.option, 'flashdir'):
        ##     os.environ['FLASH_BASEDIR'] = self.parser.option.flashdir
        ## if hasattr(self.parser.option, 'buildid'):
        ##     os.environ['FLASH_BUILDID'] = self.parser.option.buildid

    def remove_settings_opt(self):
        for e in sys.argv[1:]:
            if '--settings' in e:
                idx = sys.argv.index(e)
                sys.argv.remove(e)
                if len(sys.argv) > idx and not '--' in sys.argv[idx]:
                    del sys.argv[idx]
                break

    @action(enabled=False)
    def mtbf_daily(self):
        parser = GaiaTestOptions()
        structured.commandline.add_logging_group(parser)
        options, tests = parser.parse_args(sys.argv[1:])
        logger = structured.commandline.setup_logging(
            options.logger_name, options, {"tbpl": sys.stdout})

        runner = GaiaTestRunner(testvars=[self.options.testvars], logger=logger, **self.kwargs)
        runner.run_tests(["tests"])

    @action(enabled=True)
    def run_mtbf(self):
        mtbf.main(marionette=self.marionette, testvars=self.options.testvars, **self.kwargs)

    def execute(self):
        self.marionette.cleanup()
        self.marionette = Marionette(device_serial=self.serial, port=self.port)
        self.marionette.wait_for_port()
        # run test runner here
        self.remove_settings_opt()
        self.kwargs = {}
        if self.port:
            self.kwargs['address'] = "localhost:" + str(self.port)
        logger.info("Using address[localhost:" + str(self.port) + "]")
        self.mtbf_daily()
        self.run_mtbf()

    def pre_flash(self):
        pass

    def flash(self):
        self.shallow_flash()
        self.full_flash()
        # workaround for waiting for boot

    def post_flash(self):
        self.setup()
        self.check_version()
        self.change_memory()
        self.add_7mobile_action()
        self.enable_certified_apps_debug()

    def collect_report(self):
        pass

    def run(self):
        try:
            if self.get_free_device():
                self.mtbf_options()
                self.pre_flash()
                self.flash()
                self.port_forwarding(self.serial, self.port)
                self.post_flash()
                self.execute()
                self.collect_report()
        finally:
            self.release()

if __name__ == '__main__':
    mjr = MtbfJobRunner()

    ## use default settings if no assigned
    settings_argv = False
    for e in sys.argv[1:]:
        if '--settings' in e:
            settings_argv = True
    if settings_argv <> True:
        sys.argv.insert(1, "--settings=tasks/task_default.json")

    mjr.run()
