# Pull all dependencies for mtbf runner
#

mtbf-env = mtbf-env
virtual-env-exists = $(shell if [ -d "mtbf-env" ]; then echo "exists"; fi)

setup-combo: combo-runner virtual-env activate

delete-mtbf-env:
	@rm -rf mtbf-env

utils: combo-runner virtual-env activate lib-install github-remove b2g-flash-tool

v2.1: mtbf-v2.1 utils custom-gaia

vmaster: mtbf-vmaster utils custom-gaia

downloader: b2g-flash-tool

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

mtbf-vmaster: mtbf-driver
	@cd MTBF-Driver && git checkout master;

mtbf-v2.1: mtbf-driver
	@cd MTBF-Driver && git checkout v2.1;

combo-runner:
	@git clone https://github.com/zapion/combo-runner.git;

mtbf-driver:
	@git clone https://github.com/Mozilla-TWQA/MTBF-Driver.git;

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
