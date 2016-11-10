.PHONY: clean-pyc clean-build

help:
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-docs - remove docs"
	@echo "clean-cov - remove coverage report"
	@echo "test - run tests with the default Python"
	@echo "test27 - run tests with python2.7"
	@echo "test3 - run tests with default python and -3Wd options"
	@echo "docs - generate Sphinx HTML documentation"
	@echo "dist - package"
	@echo "pep8 - PEP-8 compliance check using flake8"
	@echo "flake8 - same as pep8"
	@echo "coverage - run coverage to check test coverage"
	 
clean: clean-build clean-pyc clean-docs clean-cov
	
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-docs:
	rm -fr htmldocs/

clean-cov:
	rm -fr htmlcov/

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
	./pep8-regression.py
	
flake8: pep8

coverage:
	coverage run --source pyslet unittests/test.py
	coverage html
	open htmlcov/index.html
	
