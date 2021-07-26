#!/bin/bash

# Run unit tests first since it activates/deactives its own virtual env
source unit_test.sh

# --------------------------------------------
# Options that must be configured by app owner
# --------------------------------------------
APP_NAME="payload-tracker"  # name of app-sre "application" folder this component lives in
COMPONENT_NAME="payload-tracker"  # name of app-sre "resourceTemplate" in deploy.yaml for this component
IMAGE="quay.io/cloudservices/payload-tracker"

# There are no current IQE plugins for payload-tracker
# IQE_PLUGINS="payload-tracker"
# IQE_MARKER_EXPRESSION="smoke"
# IQE_FILTER_EXPRESSION=""

# Install bonfire repo/initialize
CICD_URL=https://raw.githubusercontent.com/RedHatInsights/bonfire/master/cicd
curl -s $CICD_URL/bootstrap.sh > .cicd_bootstrap.sh && source .cicd_bootstrap.sh

source $CICD_ROOT/build.sh
# source $CICD_ROOT/deploy_ephemeral_env.sh
# source $CICD_ROOT/smoke_test.sh
