/*
 * Requires: https://github.com/RedHatInsights/insights-pipeline-lib
 */

@Library("github.com/RedHatInsights/insights-pipeline-lib") _

podLabel = "payload-tracker-test-${UUID.randomUUID().toString()}"

// Code coverage failure threshold
codecovThreshold = 80

// Test db settings
dbUser = "payloadtracker"
dbPassword = "payloadtracker"
dbName = "payloadtracker"
dbContainer = "payload-tracker-db"

// Test redis settings
redisContainer = "payload-tracker-redis"


pipelineUtils.cancelPriorBuilds()
pipelineUtils.runIfMasterOrPullReq {
    runStages()
}


def runStages() {
    podTemplate(label: podLabel, cloud: "openshift", containers: [
        containerTemplate(
            name: 'payload-tracker',
            image: 'python:3.6.5',
            ttyEnabled: true,
            command: 'cat',
            resourceRequestCpu: '300m',
            resourceLimitCpu: '1000m',
            resourceRequestMemory: '512Mi',
            resourceLimitMemory: '1Gi'
        ),
        containerTemplate(
            name: dbContainer,
            image: "docker-registry.default.svc:5000/buildfactory/payload-tracker-db:latest",
            ttyEnabled: true,
            envVars: [
                containerEnvVar(key: 'POSTGRESQL_USER', value: dbUser),
                containerEnvVar(key: 'POSTGRESQL_PASSWORD', value: dbPassword),
                containerEnvVar(key: 'POSTGRESQL_DATABASE', value: dbName),
            ],
            volumes: [emptyDirVolume(mountPath: '/var/lib/pgsql/data')],
            resourceRequestCpu: '50m',
            resourceLimitCpu: '200m',
            resourceRequestMemory: '64Mi',
            alwaysPullImage: true,
            resourceLimitMemory: '100Mi'
        ),
        containerTemplate(
            name: redisContainer,
            image: "docker-registry.default.svc:5000/buildfactory/redis-5:latest",
            ttyEnabled: true,
            resourceRequestCpu: '50m',
            resourceLimitCpu: '200m',
            resourceRequestMemory: '64Mi',
            alwaysPullImage: true,
            resourceLimitMemory: '100Mi'
        )
    ]) {
        node (podLabel) {
            container("payload-tracker") {
                stage('Setup environment') {
                    gitUtils.withStatusContext('setup') {
                        // check out source again to get it in this node's workspace
                        scmVars = checkout scm
                        pythonUtils.runPipenvInstall(scmVars: scmVars)
                        sh "${pipelineVars.userPath}/pipenv run alembic upgrade head"
                    }
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
    }
}