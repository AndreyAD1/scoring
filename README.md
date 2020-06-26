# scoring
This server provides an API based on POST requests.

# Project Goal
The code was written for educational purposes. 
Training course for Python developers: [OTUS.ru](https://otus.ru/lessons/razrabotchik-python/).

# Getting Started
 
## How to Install
Python v3.7 should be already installed. No third-party dependencies are required.

## Quick Start 
1. Download this repository;
2. Run the server on Linux.
```bash
$ python3 api.py
[2020.06.27 01:46:45] I Starting server at 8080
```
A user can configure the server port and a path to the log file using 
parameters `--port` and `--log` respectively.

An example of valid request: 
```bash
$ curl -X POST -H "Content-Type: application/json" -d '{"account": "horns&hoofs", "login": "h&f", "method":
"online_score", "token":
"55cc9ce545bcd144300fe9efc28e65d415b923ebb6be1e19d2750a2c03e80dd209a27954dca045e5bb12418e7d89b6d718a9e35af34e14e1d5bcd",
"arguments": {"phone": "79175002040", "email": "stupnikov@otus.ru", "first_name": "Стансилав", "last_name":
"Ступников", "birthday": "01.01.1990", "gender": 1}}' http://127.0.0.1:8080/method/
```
The module `test.py` contains more request examples. 