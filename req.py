from collections.abc import Iterable
from datetime import datetime

ADMIN_LOGIN = "admin"


class BaseDescriptor:
    def __init__(
            self,
            name: str,
            required: bool,
            nullable: bool,
            type_class
    ):
        self.name = "_" + name
        self.required = required
        self.nullable = nullable
        self.type = type_class

    def __get__(self, instance, cls):
        try:
            attribute_value = getattr(instance, self.name)
        except AttributeError:
            if self.required:
                raise AttributeError(f"{self.name} is required argument.")
            attribute_value = None

        return attribute_value

    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f"{self.name} can not be empty.")

        setattr(instance, self.name, value)


class EmailField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f"{self.name} can not be empty.")

        if value and "@" not in value:
            raise TypeError(f"{self.name} should contain a symbol '@'.")

        setattr(instance, self.name, value)


class ClientIdsField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f"{self.name} can not be empty.")

        if not all({isinstance(i, int) for i in value}):
            raise TypeError(f"All client ids should be integers.")

        setattr(instance, self.name, value)


class DateField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f"{self.name} can not be empty.")

        field_date = None
        if value:
            try:
                field_date = datetime.strptime(value, "%d.%m.%Y")
            except ValueError:
                err_msg = "{} must be a string containing a date as DD.MM.YYYY"
                raise TypeError(err_msg.format(self.name))

        setattr(instance, self.name, field_date)


class BirthdayField(BaseDescriptor):
    def __set__(self, instance, value):
        if not isinstance(value, self.type):
            raise TypeError(f"{self.name} must be {self.type}")

        if not self.nullable and not value:
            raise TypeError(f"{self.name} can not be empty.")

        birthday = None
        if value:
            try:
                birthday = datetime.strptime(value, "%d.%m.%Y")
            except ValueError:
                err_msg = "{} must be a string containing a date as DD.MM.YYYY"
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
            raise TypeError(f"{self.name} can not be empty.")

        allowed_values = [0, 1, 2]
        if value not in allowed_values:
            option_description = " or ".join([str(v) for v in allowed_values])
            raise TypeError(f"{self.name} should be {option_description}.")

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
            raise TypeError(f"{self.name} can not be empty.")

        if value:
            if str(value)[0] != "7":
                raise TypeError("A phone number should start with 7.")
            if len(str(value)) != 11:
                raise TypeError("A phone number should consist of 11 digits.")

        setattr(instance, self.name, value)

    @property
    def allowed_types_str(self) -> str:
        return " or ".join([str(typ) for typ in self.type])


class ClientsInterestsRequest:
    client_ids = ClientIdsField("client_ids", True, False, list)
    date = DateField("date", False, True, str)


class OnlineScoreRequest:
    first_name = BaseDescriptor("first_name", False, True, str)
    last_name = BaseDescriptor("last_name", False, True, str)
    email = EmailField("email", False, True, str)
    phone = PhoneField("phone", False, True, [str, int])
    birthday = BirthdayField("birthday", False, True, str)
    gender = GenderField("gender", False, True, int)


class MethodRequest:
    account = BaseDescriptor("account", False, True, str)
    login = BaseDescriptor("login", True, True, str)
    token = BaseDescriptor("token", True, True, str)
    arguments = BaseDescriptor("arguments", True, True, dict)
    method = BaseDescriptor("method", True, False, str)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN
