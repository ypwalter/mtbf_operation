# Pull all dependencies for mtbf runner
#

mtbf-env = mtbf-env
virtual-env-exists = $(shell if [ -d "mtbf-env" ]; then echo "exists"; fi)

setup-combo: combo-runner virtual-env activate

delete-mtbf-env:
	@rm -rf mtbf-env

utils: get-branch combo-runner virtual-env activate lib-install github-remove b2g-flash-tool b2g-tool

v2.2: mtbf-v2.2 utils custom-gaia

v2.1: mtbf-v2.1 utils custom-gaia

vmaster: mtbf-vmaster utils custom-gaia

downloader: b2g-flash-tool

b2g-tool:
	@git clone https://github.com/mozilla-b2g/B2G
	@cp -r B2G/tools .
	@rm -rf B2G
	@touch tools/__init__.py

virtual-env:
ifneq ($(virtual-env-exists),exists)
	@virtualenv ${mtbf-env}
else
	@echo "virtual environment exists." 
endif

custom-gaia:
ifdef gaiatest
	cp -r ${gaiatest} .
	. ${mtbf-env}/bin/activate; \
	cd $(shell basename ${gaiatest}); \
        git checkout -b ${branch} origin/${branch}; \
	python setup.py install; \
	rm -rf $(shell basename ${gaiatest})
else
	echo use default gaiatest
endif

lib-install: virtual-env
	@. ${mtbf-env}/bin/activate; \
		pip install lockfile;

activate: mtbf-driver virtual-env
	@. ${mtbf-env}/bin/activate; \
		cd MTBF-Driver; \
	    python setup.py install; \
		cd ../combo-runner; \
		python setup.py install;

github-remove:
	@rm -rf MTBF-Driver combo-runner

get-branch:
	@cd MTBF-Driver && branch=$(git branch | grep "\*" | awk '{print $2}') && cd ..;

mtbf-vmaster: mtbf-driver
	@cd MTBF-Driver && cp mtbf_driver/conf/default_v300.json mtbf_driver/conf/default.json;

mtbf-v2.2: mtbf-driver
	@cd MTBF-Driver && git checkout -b v2.2 origin/v2.2 && cp mtbf_driver/conf/default_v220.json mtbf_driver/conf/default.json;

mtbf-v2.1: mtbf-driver
	@cd MTBF-Driver && git checkout -b v2.1 origin/v2.1 && cp mtbf_driver/conf/default_v210.json mtbf_driver/conf/default.json;

combo-runner:
	@git clone https://github.com/zapion/combo-runner.git;

mtbf-driver:
	@git clone https://github.com/Mozilla-TWQA/MTBF-Driver.git; \
		cp -rf MTBF-Driver/mtbf_driver/conf .; \
		cp -rf MTBF-Driver/mtbf_driver/tests .; \
		cp -rf MTBF-Driver/mtbf_driver/runlist .;

update: 
	@cd MTBF-Driver; \
     git pull -u; \
     cd ../combo-runner; \
     git pull -u;

b2g-flash-tool:
	git clone https://github.com/Mozilla-TWQA/B2G-flash-tool.git; \
		mv B2G-flash-tool flash_tool; \
		cp b2g_download.py flash_tool;

clean:
	@rm -rf MTBF-Driver; rm -rf combo-runner; rm -rf B2G-flash-tool; rm -rf flash_tool; rm -rf ${mtbf-env}
