#!/bin/bash

#-------
# setup pipenv
#-------
pip3 install --user pipenv
pipenv install


pipenv run tests
if [ $? != 0 ]; then
    exit 1
fi

pipenv run linter
if [ $? != 0 ]; then
    exit 1
fi