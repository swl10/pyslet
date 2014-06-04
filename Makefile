.PHONY: clean-pyc clean-build

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "test - run tests with the default Python"
	@echo "test27 - run tests with python2.7"
	@echo "test3 - run tests with default python and "-3 -Wd -W module -t" options
	@echo "docs - generate Sphinx HTML documentation"
	@echo "dist - package"
	@echo "pep8 - PEP-8 compliance check using pep8"
	@echo "pep8s - PEP-8 compliance statistics using pep8"
	@echo "flake8 - PEP-8 compliance check using flake8"
	@echo "flake8s - PEP-8 compliance statistics using flake8"

clean: clean-build clean-pyc
	
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

test:
	python unittests/test.py

test27:
	python2.7 unittests/test.py

test3:
	python -3 -Wd -W module -t unittests/test.py

docs:
	rm -fr htmldocs/
	sphinx-build -b html doc htmldocs/
	open htmldocs/index.html
	
dist: clean
	python setup.py sdist
	ls -l dist

pep8:
	touch pep8-count.txt
	date >> pep8-count.txt
	-pep8 --count -qq pyslet >> pep8-count.txt 2>&1
	tail -n 4 pep8-count.txt

pep8s: pep8
	pep8 --statistics -qq pyslet
	
flake8:
	autopep8 -i -r pyslet
	touch flake8-count.txt
	date >> flake8-count.txt
	-flake8 --count -qq pyslet >> flake8-count.txt 2>&1
	tail -n 4 flake8-count.txt

flake8s: flake8
	flake8 --statistics -qq pyslet
	
