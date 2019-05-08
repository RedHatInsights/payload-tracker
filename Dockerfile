FROM registry.access.redhat.com/rhscl/python-36-rhel7

WORKDIR /usr/src/app
COPY . .

RUN scl enable rh-python36 "pip install pipenv && \
                            pipenv run pip install pip==18.0 && \
                            pipenv install"

EXPOSE 8000
EXPOSE 8080
USER 1001
CMD ["python", "app.py"]
