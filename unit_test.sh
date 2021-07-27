#!/bin/bash

cd $APP_ROOT

#-------
# setup venv for unit tests
#-------

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel pipenv
pipenv install


pipenv run tests
pipenv run linter

result=$?

deactivate

cd -

exit $result