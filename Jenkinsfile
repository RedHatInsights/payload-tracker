/*
 * Requires: https://github.com/RedHatInsights/insights-pipeline-lib
 */

@Library("github.com/RedHatInsights/insights-pipeline-lib") _

// Code coverage failure threshold
codecovThreshold = 80


node {
    pipelineUtils.cancelPriorBuilds()

    pipelineUtils.runIfMasterOrPullReq {
        runStages()
    }
}


def runStages() {
    openShiftUtils.withNode(image: "docker-registry.default.svc:5000/jenkins/jenkins-slave-base-centos7-python36:latest") {
        // check out source again to get it in this node's workspace
        scmVars = checkout scm

        stage('Pip install') {
            pythonUtils.runPipenvInstall(scmVars: scmVars)
        }

        stage('Lint') {
            pythonUtils.runLintCheck()
        }

        stage('UnitTest') {
            gitUtils.withStatusContext("unittest") {
                sh (
                    "${pipelineVars.userPath}/pipenv run python -m pytest " +
                        "--log-cli-level=debug --junitxml=junit.xml --cov-config=.coveragerc " +
                        "--cov=. --cov-report html tests/ -s -v"
                )
            }
            junit 'junit.xml'
        }

        stage('Code coverage') {
            pythonUtils.checkCoverage(threshold: codecovThreshold)
        }

        if (currentBuild.currentResult == 'SUCCESS') {
            if (env.BRANCH_NAME == 'master') {
                // Stages to run specifically if master branch was updated
            }
        }
    }
}