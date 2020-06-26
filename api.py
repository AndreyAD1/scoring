#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from collections.abc import Iterable
from datetime import datetime
import logging
import hashlib
import uuid
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Tuple, Sequence

from scoring import get_score, get_interests

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


class BaseDescriptor:
    def __init__(
            self, name: str,
            required: bool,
            nullable: bool,
            type_class
    ):
        self.name = '_' + name
        self.required = required
        self.nullable = nullable
        self.type = type_class

    def __get__(self, instance, cls):
        attribute_value = getattr(instance, self.name)
        return attribute_value

    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        setattr(instance, self.name, value)


class EmailField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        if value and '@' not in value:
            raise TypeError(f'{self.name} should contain a symbol "@".')

        setattr(instance, self.name, value)


class ClientIdsField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        if not all({isinstance(i, int) for i in value}):
            raise TypeError(f'All client ids should be integers.')

        setattr(instance, self.name, value)


class DateField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        field_date = None
        if value:
            try:
                field_date = datetime.strptime(value, '%d.%m.%Y')
            except ValueError:
                err_msg = '{} must be a string containing a date as DD.MM.YYYY'
                raise TypeError(err_msg.format(self.name))

        setattr(instance, self.name, field_date)


class BirthdayField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        birthday = None
        if value:
            try:
                birthday = datetime.strptime(value, '%d.%m.%Y')
            except ValueError:
                err_msg = '{} must be a string containing a date as DD.MM.YYYY'
                raise TypeError(err_msg.format(self.name))

        current_datetime = datetime.now()
        limit_date = current_datetime.replace(year=current_datetime.year - 70)
        if birthday < limit_date:
            raise TypeError("Person age should be less than 70 years.")

        setattr(instance, self.name, birthday)


class GenderField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        allowed_values = [0, 1, 2]
        if value not in allowed_values:
            option_description = ' or '.join([str(v) for v in allowed_values])
            raise TypeError(f'{self.name} should be {option_description}.')

        setattr(instance, self.name, value)


class PhoneField(BaseDescriptor):
    def __init__(
            self,
            name: str,
            required: bool,
            nullable: bool,
            allowed_types: Iterable
    ):
        BaseDescriptor.__init__(self, name, required, nullable, allowed_types)
        if not isinstance(allowed_types, Iterable):
            err_msg = "'allowed_types' of PhoneField should be an iterable."
            raise TypeError(err_msg)

        self.type = allowed_types

    def __set__(self, instance, value):
        if not any([isinstance(value, typ) for typ in self.type]):
            raise TypeError(f"{self.name} must be {self.allowed_types_str}")

        if not self.nullable and not value:
            raise TypeError(f'{self.name} can not be empty.')

        if value:
            if str(value)[0] != '7':
                raise TypeError('A phone number should start with 7.')
            if len(str(value)) != 11:
                raise TypeError('A phone number should consist of 11 digits.')

        setattr(instance, self.name, value)

    @property
    def allowed_types_str(self) -> str:
        return ' or '.join([str(typ) for typ in self.type])


class ClientsInterestsRequest:
    client_ids = ClientIdsField("client_ids", True, False, list)
    date = DateField("date", False, True, str)


class OnlineScoreRequest:
    first_name = BaseDescriptor('first_name', False, True, str)
    last_name = BaseDescriptor('last_name', False, True, str)
    email = EmailField('email', False, True, str)
    phone = PhoneField('phone', False, True, [str, int])
    birthday = BirthdayField('birthday', False, True, str)
    gender = GenderField('gender', False, True, int)


class MethodRequest:
    account = BaseDescriptor('account', False, True, str)
    login = BaseDescriptor('login', True, True, str)
    token = BaseDescriptor('token', True, True, str)
    arguments = BaseDescriptor('arguments', True, True, dict)
    method = BaseDescriptor('method', True, False, str)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        string_to_hash = datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        digest = hashlib.sha512(string_to_hash.encode()).hexdigest()
    else:
        string_to_hash = request.account + request.login + SALT
        digest = hashlib.sha512(string_to_hash.encode()).hexdigest()
    if digest == request.token:
        return True
    return False


def get_valid_request(request_body, request_class):
    request = request_class()
    err_msg = None
    request_params = {
        n: a for n, a in request_class.__dict__.items() if hasattr(a, "required")
    }
    for param_name, param in request_params.items():
        try:
            param_value = request_body[param_name]
        except KeyError:
            if param.required:
                request = None
                err_msg = f"Request does not contain the field '{param_name}'"
                break
            continue
        try:
            setattr(request, param_name, param_value)
        except TypeError as exception:
            request = None
            err_msg = str(exception)
            break

    return err_msg, request


def get_score_response(
        request: MethodRequest
) -> Tuple[int, Dict[str, int], List[str]]:
    """Return info of response to online score request."""
    err_message, score_req = get_valid_request(
        request.arguments,
        OnlineScoreRequest
    )
    response = err_message
    return_code = INVALID_REQUEST
    req_params = {}
    if not err_message:
        req_params = {n.lstrip('_'): v for n, v in score_req.__dict__.items()}

        positional_arg_names = ['phone', 'email']
        args = {n: None for n in positional_arg_names}

        score = get_score(
            None,
            **{**args, **req_params}
        )
        response = {"score": score}
        return_code = OK

    return return_code, response, list(req_params.keys())


def get_client_interests_response(
        request: MethodRequest,
) -> Tuple[int, Dict[int, List[str]]]:
    """Return an error code and a response to client interests request."""
    err_message, client_interests_request = get_valid_request(
        request.arguments,
        ClientsInterestsRequest
    )
    response = err_message
    return_code = INVALID_REQUEST
    if not err_message:
        client_ids = client_interests_request.client_ids
        response = {i: get_interests(1, 1) for i in client_ids}
        return_code = OK
    return return_code, response


def method_handler(request, context, store):
    request_body = request.get("body")
    return_code = INVALID_REQUEST
    response = None
    error = None
    if request_body:
        error, method_request = get_valid_request(request_body, MethodRequest)
        if method_request:
            successful_auth = check_auth(method_request)
            return_code = FORBIDDEN
            if successful_auth:
                request_method = method_request.method
                if request_method == "online_score":
                    return_code, response, filled_fields = get_score_response(
                        method_request
                    )
                    if return_code == OK:
                        context["has"] = filled_fields
                elif request_method == "clients_interests":
                    return_code, response = get_client_interests_response(
                        method_request
                    )
                    if return_code == OK:
                        context["nclients"] = len(response)
                else:
                    return_code = BAD_REQUEST

    response = response or error
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
