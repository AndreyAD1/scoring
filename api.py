#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import json
import logging
import hashlib
import uuid
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Tuple

from req import ClientsInterestsRequest, MethodRequest, OnlineScoreRequest
from scoring import get_score, get_interests

SALT = "Otus"
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
    if request.is_admin:
        return OK, {"score": 42}, []

    err_message, score_req = get_valid_request(
        request.arguments,
        OnlineScoreRequest
    )
    response = err_message
    return_code = INVALID_REQUEST
    req_params = {}
    if not err_message:
        req_params = {n.lstrip("_"): v for n, v in score_req.__dict__.items()}

        positional_arg_names = ["phone", "email"]
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
        logging.info("Successfully get request body.")
        error, method_request = get_valid_request(request_body, MethodRequest)
        if method_request:
            logging.info(f"Request is valid (id: {context.get('request_id')}.")
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
                    err_msg = f"The invalid request method {request_method}"
                    logging.error(err_msg + str(context))
                    return_code = BAD_REQUEST

    response = response or error
    return response, return_code


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        logging.info(f'Request handling started. {context}')
        request = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except:
            logging.error("Failed to read request body.")
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
        self.wfile.write(json.dumps(r).encode())
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(
        filename=opts.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S"
    )
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
