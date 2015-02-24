mtbf_operation
==============
To setup mtbf environment for lab testing.  It will help to pull dependencies, flashing and/or executing tests

For MTBF specific problem, please refer to https://github.com/Mozilla-TWQA/MTBF-Driver

Dependencies:
* MTBF-Driver
* combo-runner
* B2G-flash-tool (for flashing)
* lockfile (python library for file lock)

Recommend to use flame

=== Quick start ===

1. Clone this repo
2. Run "make vmaster"
3. Run "source mtbf-env/bin/activate" to enable virtual env
4. Run "mtbf_job_runner.py --testvars={TESTVARS} --settings=task_template.json"

Parameters:

1. --settings:  Specify a json file to define which task should be enabled/disabled
2. FLASH_bASEDIR  : system virable.  To specify directory for flashing; will only search for archives the same as files in pvt.
3. FLASH_BUILDID  : in FLASH_BASEDIR, if directory structure is the same as pvtbuild, using build id for retrieving target build artifact.


Customization:

1. To install gaia-ui-test from different path, change by gaiatest={gaiatest_path}, e.g., "make vmaster gaiatest=/gaia/tests/python/gaia-ui-tests/"
2. Install virtual environment to a specific path, use mtbf-env={venv_path}, same as #1



TODO:
* Integrating all tasks/action and run (done)
* All tasks can be run individually 
* Re-writing script to adapting new architecture
  * 7-mobile settings (done)
  * change memory size (done)
  * check resource (done)
  * environment cleanup - remove port forwarding (done)
  * memory nfs indep symbol - collect memory report (done) - force crash dump (deprecated)
  * common check gaia (done)
  * common check B2G flash tool (done)
  * virtualenv setup (done)
  * port detection (done)
  * prerun (done)
  * run mtbf multi new
  * shallow flash indep symbol
