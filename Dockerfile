FROM registry.redhat.io/ubi8/ubi-minimal

WORKDIR /usr/src/app

RUN microdnf -y install curl python36 python3-devel python3-pip which mariadb-connector-c-devel gcc
COPY . .

RUN pip3 install pipenv
RUN pipenv run pip3 install pip==18.0
RUN pipenv install --system

EXPOSE 8000
EXPOSE 8080

CMD ["python3", "./app.py"]
