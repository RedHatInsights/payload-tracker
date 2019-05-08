FROM python:3.6

WORKDIR /usr/src/app
COPY . .

RUN pip install pipenv
RUN pipenv run pip install pip==18.0
RUN pipenv install --system

EXPOSE 8000
EXPOSE 8080
USER 1001
CMD ["python", "./app.py"]
