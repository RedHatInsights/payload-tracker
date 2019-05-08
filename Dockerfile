FROM registry.access.redhat.com/rhscl/python-36-rhel7

WORKDIR /usr/src/app
COPY . .

RUN scl enable rh-python36 "pip install --upgrade pip && \
                            pip install pipenv && \
                            pipenv install --system"

EXPOSE 8000
EXPOSE 8080
USER 1001
CMD ["python", "app.py"]
