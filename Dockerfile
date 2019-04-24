FROM registry.access.redhat.com/rhscl/python-36-rhel7

WORKDIR /opt/app-root/src
COPY . .

RUN scl enable rh-python36 "pip install --upgrade pip && \
                            pip install pipenv && \
                            pipenv install --system"

EXPOSE 8000
CMD ["python", "app.py"]
