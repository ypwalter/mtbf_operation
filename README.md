mtbf_operation
==============
To setup mtbf environment for lab testing.  It will help to pull dependencies, flashing and/or executing tests

For MTBF specific problem, please refer to https://github.com/Mozilla-TWQA/MTBF-Driver

Dependencies:
* MTBF-Driver
* combo-runner
* B2G-flash-tool (for flashing)
* b2g utilities
* gaia (optional)
* lockfile (python library for file lock)

Recommend to use flame

=== Quick start ===

1. Clone this repo
2. Run "make vmaster"
3. Run "source mtbf-env/bin/activate" to enable virtual env
4. Run "mtbf_job_runner.py --testvars={TESTVARS} --settings=task_template.json"

Parameters:

1. --settings:  Specify a json file to define which task should be enabled/disabled
2. FLASH_bASEDIR  : System virable.  To specify directory for flashing; will only search for archives the same as files in pvt.
3. FLASH_BUILDID  : In FLASH_BASEDIR, if directory structure is the same as pvtbuild, using build id for retrieving target build artifact.
4. output_directory: Setting output folder so all logging information including logcat, memory report, process info, and so on.



Download build from pvt
* Using [https://github.com/Mozilla-TWQA/B2G-flash-tool | B2G-flash-tool] to do auth, downloading, flashing.
* Donwloaded build is set "pvt/" by default.
* If you only want to download builds, using b2g_downloader.py in flash_tool, it will run downloading but not flashing.



Customization:

1. To install gaia-ui-test from different path, change by gaiatest={gaiatest_path}, e.g., "make vmaster gaiatest=/gaia/tests/python/gaia-ui-tests/"
2. Install virtual environment to a specific path, use mtbf-env={venv_path}, same as #1
3. After mtbf installed, conf and runlist folders are brought to root folder automatically.

