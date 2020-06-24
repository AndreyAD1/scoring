#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import json
import datetime
import logging
import hashlib
import uuid
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class CharField:
    def __init__(self, name: str, required: bool, nullable: bool):
        self.name = '_' + name
        self.required = required
        self.nullable = nullable

    def __get__(self, instance, cls):
        attribute_value = getattr(instance, self.name)
        return attribute_value

    def __set__(self, instance, value):
        if not isinstance(value, str):
            raise TypeError(f'{self.name} must be a string')

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be an empty string.')

        setattr(instance, self.name, value)


class ArgumentsField:
    def __init__(self, name: str, required: bool, nullable: bool):
        self.name = '_' + name
        self.required = required
        self.nullable = nullable

    def __get__(self, instance, cls):
        attribute_value = getattr(instance, self.name)
        return attribute_value

    def __set__(self, instance, value):
        if not isinstance(value, dict):
            raise TypeError('Must be a dict')

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be an empty dict.')

        setattr(instance, self.name, value)


class EmailField(CharField):
    pass


class PhoneField:
    pass


class DateField:
    def __init__(self, name: str, required: bool):
        self.name = '_' + name
        self.required = required

    def __get__(self, instance, cls):
        attribute_value = getattr(instance, self.name)
        return attribute_value

    def __set__(self, instance, value):
        if value and not isinstance(value, str):
            raise TypeError(f'{self.name} must be a string')

        if value:
            try:
                datetime.datetime.strptime(value, '%d.%m.%Y')
            except ValueError:
                err_msg = '{} must be a string containing a date as DD.MM.YYYY'
                raise TypeError(err_msg.format(self.name))

        setattr(instance, self.name, value)


class BirthDayField:
    pass


class GenderField:
    pass


class ClientIDsField:
    def __init__(self, name: str, required: bool):
        self.name = '_' + name
        self.required = required

    def __get__(self, instance, cls):
        attribute_value = getattr(instance, self.name)
        return attribute_value

    def __set__(self, instance, value):
        if not isinstance(value, list):
            raise TypeError(f'{self.name} must be a list')

        if not value:
            raise TypeError(f'{self.name} can not be an empty list.')

        setattr(instance, self.name, value)


class ClientsInterestsRequest:
    client_ids = ClientIDsField("client_ids", required=True)
    date = DateField("date", required=False)
#
#
# class OnlineScoreRequest:
#     first_name = CharField(required=False, nullable=True)
#     last_name = CharField(required=False, nullable=True)
#     email = EmailField(required=False, nullable=True)
#     phone = PhoneField(required=False, nullable=True)
#     birthday = BirthDayField(required=False, nullable=True)
#     gender = GenderField(required=False, nullable=True)


class MethodRequest:
    account = CharField('account', required=False, nullable=True)
    login = CharField('login', required=True, nullable=True)
    token = CharField('token', required=True, nullable=True)
    arguments = ArgumentsField('arguments', required=True, nullable=True)
    method = CharField('method', required=True, nullable=True)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        string_to_hash = datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        digest = hashlib.sha512(string_to_hash.encode()).hexdigest()
    else:
        string_to_hash = request.account + request.login + SALT
        digest = hashlib.sha512(string_to_hash.encode()).hexdigest()
    if digest == request.token:
        return True
    return False


def method_handler(request, ctx, store):
    request_body = request.get("body")
    return_code = INVALID_REQUEST
    if request_body:
        method_request = MethodRequest()
        try:
            method_request.login = request_body.get("login")
            method_request.token = request_body.get("token")
            method_request.method = request_body.get("method")
            method_request.arguments = request_body.get("arguments")
            if request_body.get("account") is not None:
                method_request.account = request_body.get("account")
            request_is_correct = True
        except TypeError:
            request_is_correct = False

        if request_is_correct:
            successful_auth = check_auth(method_request)
            return_code = FORBIDDEN
            if successful_auth:
                return_code = OK

    response = ERRORS.get(return_code) or 'Fake correct response'
    return response, return_code


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers},
                        context,
                        self.store
                    )
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO,
        format='[%(asctime)s] %(levelname).1s %(message)s',
        datefmt='%Y.%m.%d %H:%M:%S'
    )
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
