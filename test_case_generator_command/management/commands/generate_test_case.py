import ast
import os
import re

import astor
from faker import Faker
from django.db import models
from django.views import View
from django.conf import settings
from django.http import HttpRequest
from django.db.models.query import QuerySet
from django.urls import get_resolver, reverse
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from rest_framework.permissions import IsAuthenticated
from django.urls.resolvers import RoutePattern, RegexPattern


class Command(BaseCommand):
    help = "Generate test cases for django rest views."

    def __init__(self):
        """Init Method to store all the global variables."""
        # initializing faker for generating fake data.
        self.fake = Faker()

        # path the to main project folder.
        self.project_dir = settings.BASE_DIR

        # Get all the installed apps.
        self.installed_apps = settings.INSTALLED_APPS

        # User created apps by using django's command to holdall the project user logic.
        self.user_created_apps = []

        # All the url pattern obs from user created apps.
        self.matched_url_pattern_objs = []

        # base test class name.
        self.base_test_class_name = "CustomTestCase"

        # initiating user model.
        self.User = get_user_model()

        # Login username and password keys.
        self.login_username = self.User.USERNAME_FIELD
        self.login_password = "password"

        # login user credentials.
        self.login_username_value = self.fake.email()
        self.login_password_value = self.fake.password()

        super().__init__()

    def generate_payload_using_model(
        self,
        obj,
        fetch_required_fields=True,
        is_login_user=False,
        is_wrong_data=False
    ):
        """Method is used to generate payload dict by using model obj."""
        fields = obj._meta.get_fields()

        fields_payload = {}

        primary_key_field = None
        for field in fields:
            try:
                if field.primary_key:
                    primary_key_field = field.name
            except AttributeError:
                pass

        for field in fields:
            if isinstance(field, models.Field):
                if (
                    (
                        (fetch_required_fields and not field.null)
                        | (not fetch_required_fields)
                    )
                    and primary_key_field is not field.name
                    and (
                        (
                            is_login_user
                            and field.name
                            not in [
                                "is_superuser",
                                "is_staff",
                                "is_active",
                                "groups",
                                "user_permissions",
                            ]
                        )
                        | (not is_login_user)
                    )
                ):
                    if field.name == self.login_username:
                        fields_payload[field.name] = self.login_username_value
                    elif field.name == self.login_password:
                        fields_payload[field.name] = self.login_password_value
                    else:
                        if isinstance(field, models.EmailField):
                            if not is_wrong_data:
                                fields_payload[field.name] = self.fake.email()
                            else:
                                fields_payload[field.name] = self.fake.full_name()
                        elif isinstance(field, models.CharField):
                            if not is_wrong_data:
                                max_length = (
                                    field.max_length
                                    if hasattr(field, "max_length")
                                    else 100
                                )
                                fields_payload[field.name] = self.fake.sentence()[
                                    :max_length
                                ].rstrip(".")
                            else:
                                fields_payload[field.name] = ""
                        elif isinstance(field, models.BooleanField):
                            if not is_wrong_data:
                                fields_payload[field.name] = True
                            else:
                                fields_payload[field.name] = "true"
                        elif isinstance(field, models.DateTimeField):
                            if not is_wrong_data:
                                fields_payload[field.name] = (
                                    self.fake.date_time().isoformat()
                                )
                            else:
                                fields_payload[field.name] = str(self.fake.date())
                        else:
                            fields_payload[field.name] = {}
        return fields_payload

    def generate_base_test_case_class(self):
        """

        """
        test_manager_dir = os.path.join(self.project_dir, "utils")
        test_manager_file_path = os.path.join(test_manager_dir, "test_manager.py")

        # Create utils folder if it doesn't exist
        if not os.path.exists(test_manager_dir):
            os.makedirs(test_manager_dir)

        # if test_manager.py not exists, then we need to create an empty test_manager.py file.
        if not os.path.isfile(test_manager_file_path):
            with open(test_manager_file_path, "w"):
                pass

        # reading the content of the file and creating tree using ast module.
        with open(test_manager_file_path, "r") as file:
            # Read the content of the file
            file_content = file.read()
        tree = ast.parse(file_content)

        # import statement checks.
        import_exist = {
            "faker": {"name": "Faker", "module": "faker", "value": False},
            "test_case": {
                "name": "APITestCase",
                "module": "rest_framework.test",
                "value": False,
            },
            "user_model": {
                "name": "get_user_model",
                "module": "django.contrib.auth",
                "value": False,
            },
        }
        for node in ast.walk(tree):  # checking if import is exist or not.
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == import_exist["test_case"]["name"]:
                        import_exist["test_case"]["value"] = True
                    elif alias.name == import_exist["user_model"]["name"]:
                        import_exist["user_model"]["value"] = True
                    elif alias.name == import_exist["faker"]["name"]:
                        import_exist["faker"]["value"] = True

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == import_exist["test_case"]["name"]:
                        import_exist["test_case"]["value"] = True
                    elif alias.name == import_exist["user_model"]["name"]:
                        import_exist["user_model"]["value"] = True
                    elif alias.name == import_exist["faker"]["name"]:
                        import_exist["faker"]["value"] = True

        for import_exist_keys in import_exist.keys():
            if not import_exist[import_exist_keys][
                "value"
            ]:  # add import statement if not exist.
                import_node = ast.ImportFrom(
                    module=import_exist[import_exist_keys]["module"],
                    names=[
                        ast.alias(
                            name=import_exist[import_exist_keys]["name"],
                            asname=None,
                        ),
                    ],
                    level=0,
                )
                tree.body.insert(0, import_node)
                modified_code = ast.unparse(tree)
                with open(test_manager_file_path, "w") as file:
                    file.write(modified_code)

        classes = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]

        if self.base_test_class_name not in classes:

            # creating base class node.
            class_comment = ast.Expr(
                value=ast.Constant(
                    value="Creating class for the Base test class that should hold all the common logic.",
                ),
            )
            class_node = ast.ClassDef(
                name=self.base_test_class_name,
                bases=[ast.Name(id="APITestCase", ctx=ast.Load())],
                body=[class_comment],
                decorator_list=[],
                keywords=[],
                lineno=2,
                col_offset=0,
            )

            # creating setup method.
            method_setup_args = ast.arguments(
                args=[ast.arg(arg="self", annotation=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                posonlyargs=[],
                defaults=[],
            )

            assign_faker_node = ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="fake",
                        ctx=ast.Store(),
                    ),
                ],
                value=ast.Call(
                    func=ast.Name(id="Faker", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
            )
            assign_user_model_node = ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="user_model",
                        ctx=ast.Store(),
                    ),
                ],
                value=ast.Call(
                    func=ast.Name(id="get_user_model", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
            )

            assign_login_creds_variable_node = ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="login_creds",
                        ctx=ast.Store(),
                    ),
                ],
                value=ast.Dict(
                    keys=[
                        ast.Constant(self.login_username),
                        ast.Constant(self.login_password),
                    ],
                    values=[
                        ast.Constant(self.login_username_value),
                        ast.Constant(self.login_password_value),
                    ],
                ),
            )

            register_payload = self.generate_payload_using_model(
                self.User,
                fetch_required_fields=True,
                is_login_user=True,
            )
            assign_user_register_variable_node = ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="register_user_data",
                        ctx=ast.Store(),
                    ),
                ],
                value=ast.Dict(
                    keys=[ast.Constant(value=k) for k in register_payload.keys()],
                    values=[ast.Constant(value=v) for v in register_payload.values()],
                ),
            )

            assign_user_register_node = ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id="self", ctx=ast.Load()),
                        attr="user",
                        ctx=ast.Store(),
                    ),
                ],
                # target = self.user
                value=ast.Call(  # value = self.user_model.objects.create_user(**self.register_user_data)
                    func=ast.Attribute(  # self.user_model.objects
                        value=ast.Attribute(  # self.user_model
                            value=ast.Name(id="self", ctx=ast.Load()),  # self
                            attr="user_model",  # user_model attribute
                            ctx=ast.Load(),
                        ),
                        attr="objects.create_user",  # objects attribute
                        ctx=ast.Load(),
                    ),
                    args=[],
                    keywords=[
                        ast.keyword(arg=None, value=ast.Name(id='self.register_user_data', ctx=ast.Load()))
                    ],
                ),
            )

            method_setup_comment = ast.Expr(
                value=ast.Constant(
                    value=f"Method to setup users/model objects and initialize required variables.",
                ),
            )

            method_setup_node = ast.FunctionDef(
                name="setUp",
                args=method_setup_args,
                body=[
                    method_setup_comment,
                    assign_faker_node,
                    assign_user_model_node,
                    assign_login_creds_variable_node,
                    assign_user_register_variable_node,
                    assign_user_register_node,
                ],
                decorator_list=[],
                lineno=1,
            )

            method_user_auth_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='client',
                            ctx=ast.Load()
                        ),
                        attr='force_authenticate',
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[
                        ast.keyword(
                            arg='user',
                            value=ast.Attribute(
                                value=ast.Name(id='self', ctx=ast.Load()),
                                attr='user',
                                ctx=ast.Load()
                            )
                        )
                    ]
                )
            )

            method_auth_user_comment = ast.Expr(
                value=ast.Constant(
                    value=f"Method to write login authentication for the user.",
                ),
            )

            method_authenticate_user_node = ast.FunctionDef(
                name="authenticate_user",
                args=method_setup_args,
                body=[
                    method_auth_user_comment,
                    method_user_auth_node
                ],
                decorator_list=[],
            )

            # combining class and method node and write on the file.
            class_node.body.append(method_setup_node)
            class_node.body.append(method_authenticate_user_node)
            tree.body.append(class_node)
            generated_code = astor.to_source(tree)
            with open(test_manager_file_path, "w") as file:
                file.write(generated_code)

    def get_user_created_apps_list(self):
        """Method to get all the app names that user created."""
        self.user_created_apps = [
            app
            for app in self.installed_apps
            if not app.startswith("django.")
            and os.path.isdir(os.path.join(self.project_dir, app.replace(".", "/")))
        ]
        print("*** User created Django Apps found ***")
        for i, user_created_app in enumerate(self.user_created_apps):
            print(f"App {i+1}: {user_created_app}")
        print()

    def filter_url_pattern_objs(self):
        """Method to filter all the url pattern objs from the user created apps and list down from urls.py"""
        resolver = get_resolver()
        url_patterns = []

        # Loop through each pattern and store its details (url and view name)
        for pattern in resolver.url_patterns:
            if hasattr(pattern, "url_patterns"):  # for include()'d url patterns
                for subpattern in pattern.url_patterns:
                    url_patterns.append(subpattern)
            else:
                url_patterns.append(pattern)

        # Filter through all the matched URLs from user created apps.
        print("*** Filtering all the Non Compatible APIs ***")
        matched_url_views = []
        for pattern in url_patterns:
            callback = pattern.callback
            if callback:
                if hasattr(callback, 'view_class') and hasattr(callback, "__module__") and hasattr(callback, "__name__"):
                    # If it's a regular function or method, get module and function name
                    module_name = callback.__module__
                    module_name = module_name.split(".")[0]
                    if module_name in self.user_created_apps:
                        matched_url_views.append(pattern)
                else:
                    print(f"URL: {pattern.pattern}, API is a non-standard class based view: Skipping")
            else:
                print(f"URL: {pattern.pattern}, No view associated: Skipping")

        print()

        self.matched_url_pattern_objs = matched_url_views

    def add_test_case_import_statement(self, tree, test_file_dir):
        """Method to add import statement if not exist in the file."""
        # checking if APITestCase import is exist, if not then add import line at the starting of file.
        import_exist = {
            "test_case": {
                "name": self.base_test_class_name,
                "module": "utils.test_manager",
                "value": False,
            },
            "url_reverse": {
                "name": "reverse",
                "module": "django.urls",
                "value": False
            },
            "status_codes": {
                "name": "status",
                "module": "rest_framework",
                "value": False
            },
        }
        for node in ast.walk(tree):  # checking if import is exist or not.
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == import_exist["test_case"]["name"]:
                        import_exist["test_case"]["value"] = True
                    elif alias.name == import_exist["url_reverse"]["name"]:
                        import_exist["url_reverse"]["value"] = True

            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == import_exist["test_case"]["name"]:
                        import_exist["test_case"]["value"] = True
                    elif alias.name == import_exist["url_reverse"]["name"]:
                        import_exist["url_reverse"]["value"] = True
                    elif alias.name == import_exist["status_codes"]["name"]:
                        import_exist["status_codes"]["value"] = True

        for import_exist_keys in import_exist.keys():
            if not import_exist[import_exist_keys][
                "value"
            ]:  # add import statement if not exist.
                import_node = ast.ImportFrom(
                    module=import_exist[import_exist_keys]["module"],
                    names=[
                        ast.alias(
                            name=import_exist[import_exist_keys]["name"],
                            asname=None,
                        ),
                    ],
                    level=0,
                )
                tree.body.insert(0, import_node)
                modified_code = ast.unparse(tree)
                with open(test_file_dir, "w") as file:
                    file.write(modified_code)

    def add_from_import_statement(self, tree, import_name, module_name, file_dir):
        """
        Method to add import statement at top if missing.
        """
        import_exists = False
        for node in ast.walk(tree):  # checking if import is exist or not.
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == import_name:
                        import_exists = True

        if not import_exists:  # add import statement if not exist.
            import_node = ast.ImportFrom(
                module=module_name,
                names=[
                    ast.alias(
                        name=import_name,
                        asname=None,
                    ),
                ],
                level=0,
            )
            tree.body.insert(0, import_node)
            modified_code = ast.unparse(tree)
            with open(file_dir, "w") as file:
                file.write(modified_code)

    def setup_method(self, reverse_url_name, tree, test_file_dir, is_auth_required, model_name, model_obj):
        """
        Method to define and definition for the setup method.
        """
        # creating setup method.
        method_setup_comment = ast.Expr(
            value=ast.Constant(
                value=f"Method to setup users/model objects and initialize required variables.",
            ),
        )
        method_setup_args = ast.arguments(
            args=[ast.arg(arg="self", annotation=None)],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            posonlyargs=[],
            defaults=[],
        )
        assignment_url_node = ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="url",
                    ctx=ast.Store(),
                ),
            ],
            value=ast.Call(
                func=ast.Name(id="reverse", ctx=ast.Load()),
                args=[ast.Constant(value=reverse_url_name)],
                keywords=[],
            ),
        )

        if model_obj:
            model_payload = self.generate_payload_using_model(model_obj)
        else:
            model_payload = {}

        assign_test_data_variable_node = ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="test_data",
                    ctx=ast.Store(),
                ),
            ],
            value=ast.Dict(
                keys=[ast.Constant(value=k) for k in model_payload.keys()],
                values=[ast.Constant(value=v) for v in model_payload.values()],
            ),
        )

        if model_obj:
            self.add_from_import_statement(tree, model_name, ".models", test_file_dir)
        assign_test_model_instance_node = ast.Assign(
            targets=[ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr="test_model_instance",
                ctx=ast.Store())],
            value=ast.Name(
                id=model_name if model_obj else "None",
                ctx=ast.Load()
            )
        )

        assign_test_model_node = ast.Assign(
            targets=[ast.Attribute(
                value=ast.Name(id='self', ctx=ast.Load()),
                attr="test_model",
                ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=model_name, ctx=ast.Load()),
                    attr='objects.create',
                    ctx=ast.Load()),
                args=[],
                keywords=[ast.keyword(arg=None, value=ast.Name(id='self.test_data', ctx=ast.Load()))]
            ) if model_obj else ast.Constant(value="None")
        )

        call_auth_login_node = ast.Expr(value=ast.Name(id="", ctx=ast.Load()))
        if is_auth_required:
            call_auth_login_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='authenticate_user',
                        ctx=ast.Load()
                    ),
                    args=[],  # No arguments
                    keywords=[]
                )
            )

        super_call_setup_node = ast.Expr(
            ast.Call(
                func=ast.Attribute(
                    value=ast.Call(
                        func=ast.Name(id="super", ctx=ast.Load()),
                        args=[],
                        keywords=[],
                    ),
                    attr="setUp",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            ),
        )

        method_setup_node = ast.FunctionDef(
            name="setUp",
            args=method_setup_args,
            body=[
                method_setup_comment,
                super_call_setup_node,
                assignment_url_node,
                assign_test_data_variable_node,
                assign_test_model_instance_node,
                assign_test_model_node,
                call_auth_login_node,
            ],
            decorator_list=[],
            lineno=1,
        )
        return method_setup_node

    def get_method_test_case(self, test_case_name, is_auth_required):
        """
        Method to create test case for the get method.
        """
        # list for the methods node to return.
        method_node_list = []

        method_get_test_case_args = ast.arguments(
            args=[ast.arg(arg="self", annotation=None)],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            posonlyargs=[],
            defaults=[],
        )

        # list test case method.
        method_list_test_case_comment = ast.Expr(
            value=ast.Constant(
                value=f"Method to write a test case for the {test_case_name} to test the list data.",
            ),
        )
        assign_api_call_node = ast.Assign(
            targets=[ast.Name(id='response', ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='client',
                        ctx=ast.Load()
                    ),
                    attr='get',
                    ctx=ast.Load()
                ),
                args=[ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='url',
                    ctx=ast.Load())],
                keywords=[]
            )
        )

        response_status_check_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Attribute(
                        value=ast.Name(id='response', ctx=ast.Load()),
                        attr='status_code',
                        ctx=ast.Load()
                    ),
                    ast.Attribute(
                        value=ast.Name(id='status', ctx=ast.Load()),
                        attr='HTTP_200_OK',
                        ctx=ast.Load()
                    )
                ],
                keywords=[]
            )
        )

        response_assert_equal_1_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Call(
                        func=ast.Name(id='len', ctx=ast.Load()),
                        args=[
                            ast.Attribute(
                                value=ast.Name(id='response', ctx=ast.Load()),
                                attr='data',
                                ctx=ast.Load()
                            )
                        ],
                        keywords=[]
                    ),
                    ast.Constant(value=1)
                ],
                keywords=[]
            )
        )

        method_node_list.append(ast.FunctionDef(
            name=f"test_get_{test_case_name}_list",
            args=method_get_test_case_args,
            body=[
                method_list_test_case_comment,
                assign_api_call_node,
                response_status_check_node,
                response_assert_equal_1_node,
            ],
            decorator_list=[],
            lineno=1,
        ))

        # empty list test case method.
        method_list_test_case_comment = ast.Expr(
            value=ast.Constant(
                value=f"Method to write a test case for the {test_case_name} to test the empty list data.",
            ),
        )
        item_delete_with_comment_node = ast.Module(
            body=[
                ast.Expr(
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Attribute(
                                value=ast.Name(id="self.test_model_instance", ctx=ast.Load()),
                                attr='objects.all()',
                                ctx=ast.Load()
                            ),
                            attr='delete',
                            ctx=ast.Load()
                        ),
                        args=[],
                        keywords=[]
                    )
                )
            ]
        )
        assign_api_call_node = ast.Assign(
            targets=[ast.Name(id='response', ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='client',
                        ctx=ast.Load()
                    ),
                    attr='get',
                    ctx=ast.Load()
                ),
                args=[ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='url',
                    ctx=ast.Load())],
                keywords=[]
            )
        )

        response_status_check_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Attribute(
                        value=ast.Name(id='response', ctx=ast.Load()),
                        attr='status_code',
                        ctx=ast.Load()
                    ),
                    ast.Attribute(
                        value=ast.Name(id='status', ctx=ast.Load()),
                        attr='HTTP_200_OK',
                        ctx=ast.Load()
                    )
                ],
                keywords=[]
            )
        )

        response_assert_equal_1_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Call(
                        func=ast.Name(id='len', ctx=ast.Load()),
                        args=[
                            ast.Attribute(
                                value=ast.Name(id='response', ctx=ast.Load()),
                                attr='data',
                                ctx=ast.Load()
                            )
                        ],
                        keywords=[]
                    ),
                    ast.Constant(value=0)
                ],
                keywords=[]
            )
        )

        method_node_list.append(ast.FunctionDef(
            name=f"test_get_empty_{test_case_name}_list",
            args=method_get_test_case_args,
            body=[
                method_list_test_case_comment,
                item_delete_with_comment_node,
                assign_api_call_node,
                response_status_check_node,
                response_assert_equal_1_node,
            ],
            decorator_list=[],
            lineno=1,
        ))

        # get list without authenticated.
        if is_auth_required:
            method_list_test_case_comment = ast.Expr(
                value=ast.Constant(
                    value=f"Method to write a test case for the {test_case_name} to test the list data without authentication.",
                ),
            )
            logout_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='client',
                            ctx=ast.Load()
                        ),
                        attr='logout',
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[]
                )
            )
            assign_api_call_node = ast.Assign(
                targets=[ast.Name(id='response', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='client',
                            ctx=ast.Load()
                        ),
                        attr='get',
                        ctx=ast.Load()
                    ),
                    args=[ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='url',
                        ctx=ast.Load())],
                    keywords=[]
                )
            )

            response_status_check_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='assertEqual',
                        ctx=ast.Load()
                    ),
                    args=[
                        ast.Attribute(
                            value=ast.Name(id='response', ctx=ast.Load()),
                            attr='status_code',
                            ctx=ast.Load()
                        ),
                        ast.Attribute(
                            value=ast.Name(id='status', ctx=ast.Load()),
                            attr='HTTP_401_UNAUTHORIZED',
                            ctx=ast.Load()
                        )
                    ],
                    keywords=[]
                )
            )

            method_node_list.append(ast.FunctionDef(
                name=f"test_get_{test_case_name}_without_authenticated",
                args=method_get_test_case_args,
                body=[
                    method_list_test_case_comment,
                    logout_node,
                    assign_api_call_node,
                    response_status_check_node,
                ],
                decorator_list=[],
                lineno=1,
            ))

        return method_node_list

    def create_method_test_case(self, test_case_name, is_auth_required, model_obj):
        """
        Method to create test case for the create method.
        """
        # list for the methods node to return.
        method_node_list = []

        method_create_test_case_args = ast.arguments(
            args=[ast.arg(arg="self", annotation=None)],
            vararg=None,
            kwonlyargs=[],
            kw_defaults=[],
            posonlyargs=[],
            defaults=[],
        )

        # create test case method.
        method_create_test_case_comment = ast.Expr(
            value=ast.Constant(
                value=f"Method to write a test case for the {test_case_name} to test the create data.",
            ),
        )
        assign_api_call_node = ast.Assign(
            targets=[ast.Name(id='response', ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='client',
                        ctx=ast.Load()
                    ),
                    attr='post',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='url',
                        ctx=ast.Load()
                    ),
                    ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='test_data',
                        ctx=ast.Load()
                    )
                ],
                keywords=[]
            )
        )

        response_status_check_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Attribute(
                        value=ast.Name(id='response', ctx=ast.Load()),
                        attr='status_code',
                        ctx=ast.Load()
                    ),
                    ast.Attribute(
                        value=ast.Name(id='status', ctx=ast.Load()),
                        attr='HTTP_201_CREATED',
                        ctx=ast.Load()
                    )
                ],
                keywords=[]
            )
        )

        response_assert_equal_1_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Call(
                        func=ast.Name(id='len', ctx=ast.Load()),
                        args=[
                            ast.Attribute(
                                value=ast.Name(id='response', ctx=ast.Load()),
                                attr='data',
                                ctx=ast.Load()
                            )
                        ],
                        keywords=[]
                    ),
                    ast.Constant(value=2)
                ],
                keywords=[]
            )
        )

        method_node_list.append(ast.FunctionDef(
            name=f"test_create_{test_case_name}_data",
            args=method_create_test_case_args,
            body=[
                method_create_test_case_comment,
                assign_api_call_node,
                response_status_check_node,
                response_assert_equal_1_node,
            ],
            decorator_list=[],
            lineno=1,
        ))

        # invalid payload create test case method.
        method_create_test_case_comment = ast.Expr(
            value=ast.Constant(
                value=f"Method to write a test case for the {test_case_name} to test the invalid payload data.",
            ),
        )

        if model_obj:
            model_payload = self.generate_payload_using_model(model_obj, is_wrong_data=True)
        else:
            model_payload = {}

        assign_test_invalid_data_variable_node = ast.Assign(
            targets=[
                ast.Attribute(
                    value=ast.Name(id="self", ctx=ast.Load()),
                    attr="invalid_test_data",
                    ctx=ast.Store(),
                ),
            ],
            value=ast.Dict(
                keys=[ast.Constant(value=k) for k in model_payload.keys()],
                values=[ast.Constant(value=v) for v in model_payload.values()],
            ),
        )

        assign_api_call_node = ast.Assign(
            targets=[ast.Name(id='response', ctx=ast.Store())],
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='client',
                        ctx=ast.Load()
                    ),
                    attr='post',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='url',
                        ctx=ast.Load()
                    ),
                    ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='invalid_test_data',
                        ctx=ast.Load()
                    )
                ],
                keywords=[]
            )
        )

        response_status_check_node = ast.Expr(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id='self', ctx=ast.Load()),
                    attr='assertEqual',
                    ctx=ast.Load()
                ),
                args=[
                    ast.Attribute(
                        value=ast.Name(id='response', ctx=ast.Load()),
                        attr='status_code',
                        ctx=ast.Load()
                    ),
                    ast.Attribute(
                        value=ast.Name(id='status', ctx=ast.Load()),
                        attr='HTTP_400_BAD_REQUEST',
                        ctx=ast.Load()
                    )
                ],
                keywords=[]
            )
        )

        method_node_list.append(ast.FunctionDef(
            name=f"test_create_invalid_{test_case_name}_data",
            args=method_create_test_case_args,
            body=[
                method_create_test_case_comment,
                assign_test_invalid_data_variable_node,
                assign_api_call_node,
                response_status_check_node,
            ],
            decorator_list=[],
            lineno=1,
        ))

        # get list without authenticated.
        if is_auth_required:
            method_create_test_case_comment = ast.Expr(
                value=ast.Constant(
                    value=f"Method to write a test case for the {test_case_name} to test the payload data without authentication.",
                ),
            )
            logout_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='client',
                            ctx=ast.Load()
                        ),
                        attr='logout',
                        ctx=ast.Load()
                    ),
                    args=[],
                    keywords=[]
                )
            )
            assign_api_call_node = ast.Assign(
                targets=[ast.Name(id='response', ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='client',
                            ctx=ast.Load()
                        ),
                        attr='post',
                        ctx=ast.Load()
                    ),
                    args=[
                        ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='url',
                            ctx=ast.Load()
                        ),
                        ast.Attribute(
                            value=ast.Name(id='self', ctx=ast.Load()),
                            attr='test_data',
                            ctx=ast.Load()
                        ),
                    ],
                    keywords=[]
                )
            )

            response_status_check_node = ast.Expr(
                value=ast.Call(
                    func=ast.Attribute(
                        value=ast.Name(id='self', ctx=ast.Load()),
                        attr='assertEqual',
                        ctx=ast.Load()
                    ),
                    args=[
                        ast.Attribute(
                            value=ast.Name(id='response', ctx=ast.Load()),
                            attr='status_code',
                            ctx=ast.Load()
                        ),
                        ast.Attribute(
                            value=ast.Name(id='status', ctx=ast.Load()),
                            attr='HTTP_401_UNAUTHORIZED',
                            ctx=ast.Load()
                        )
                    ],
                    keywords=[]
                )
            )

            method_node_list.append(ast.FunctionDef(
                name=f"test_create_{test_case_name}_without_authenticated",
                args=method_create_test_case_args,
                body=[
                    method_create_test_case_comment,
                    logout_node,
                    assign_api_call_node,
                    response_status_check_node,
                ],
                decorator_list=[],
                lineno=1,
            ))

        return method_node_list

    def update_method_test_case(self, test_case_name, is_auth_required):
        """
        Method to create test case for the update method.
        """
        # list for the methods node to return.
        method_node_list = []

        return method_node_list

    def retrieve_method_test_case(self, test_case_name, is_auth_required):
        """
        Method to create test case for the retrieve method.
        """
        # list for the methods node to return.
        method_node_list = []

        return method_node_list

    def destroy_method_test_case(self, test_case_name, is_auth_required):
        """
        Method to create test case for the destroy method.
        """
        # list for the methods node to return.
        method_node_list = []

        return method_node_list

    def handle(self, *args, **kwargs):
        """This Method will handle all the major business logic for the command."""

        # check if BASE_DIR is correctly set or not.
        expected_base_dir_file = os.path.join(settings.BASE_DIR, 'manage.py')
        if not os.path.exists(expected_base_dir_file):
            print(f"BASE_DIR might be incorrect, it should be pointing to the root folder of your project: {settings.BASE_DIR}")
            return False

        # create utils - base test case file.
        self.generate_base_test_case_class()

        # Filter out system apps and installed Python packages
        self.get_user_created_apps_list()

        # Filter out all the url pattern objs from the user created apps.
        self.filter_url_pattern_objs()

        # Looping through all the matched url pattern objs so that we can create test case for each of them.
        print("*** Test cases created for these APIs ***")
        for test_case_api_class in self.matched_url_pattern_objs:
            # initiating all the important variables.
            module_name = test_case_api_class.callback.__module__
            reverse_url_name = test_case_api_class.name
            url_keywords = {}
            if isinstance(test_case_api_class.pattern, RoutePattern):
                url_keywords_list = re.findall(
                    r"<(\w+):(\w+)>",
                    str(test_case_api_class.pattern),
                )
                for value, key in url_keywords_list:
                    value_data = None
                    if value == "int":
                        value_data = self.fake.random_int()
                    elif value == "str":
                        value_data = self.fake.first_name()
                    url_keywords[key] = value_data
            elif isinstance(test_case_api_class.pattern, RegexPattern):
                url_keywords_list = re.findall(
                    r"\?P<(\w+)>",
                    str(test_case_api_class.pattern),
                )
                for value in url_keywords_list:
                    url_keywords[value] = self.fake.random_int()

            full_url = reverse(reverse_url_name, kwargs=url_keywords)
            module_name = module_name.split(".")[0]
            api_name = test_case_api_class.callback.view_class.__name__
            api_name = re.sub(r"(view|views|api)", "", api_name, flags=re.IGNORECASE)
            is_auth_required = False
            permission_classes_list = getattr(test_case_api_class.callback.view_class, "permission_classes", None)
            if permission_classes_list:
                for permission in permission_classes_list:
                    if permission == IsAuthenticated:
                        is_auth_required = True
            test_case_name_upper_case = api_name + "TestCase"
            test_case_name_lower_case = re.sub(
                r"^_",
                "",
                re.sub(r"([A-Z])", r"_\1", api_name).lower(),
            )
            test_file_dir = os.path.join(self.project_dir, module_name, "tests.py")
            supported_methods = []
            if isinstance(test_case_api_class.callback.view_class, type) and issubclass(
                test_case_api_class.callback.view_class,
                View,
            ):
                if hasattr(test_case_api_class.callback.view_class, "list") or (hasattr(test_case_api_class.callback.view_class, "get") and len(url_keywords.keys()) == 0):
                    supported_methods.append("list")
                if hasattr(test_case_api_class.callback.view_class, "create") or hasattr(test_case_api_class.callback.view_class, "post"):
                    supported_methods.append("create")
                if hasattr(test_case_api_class.callback.view_class, "update") or hasattr(test_case_api_class.callback.view_class, "patch"):
                    supported_methods.append("update")
                if hasattr(test_case_api_class.callback.view_class, "destroy") or hasattr(test_case_api_class.callback.view_class, "delete"):
                    supported_methods.append("destroy")
                if hasattr(test_case_api_class.callback.view_class, "retrieve") or (hasattr(test_case_api_class.callback.view_class, "get") and len(url_keywords.keys()) > 0):
                    supported_methods.append("retrieve")

            supported_method_for_api = supported_methods[0]
            supported_method_for_api = "delete" if supported_method_for_api == "destroy" else "post" if supported_method_for_api == "create" else "patch" if supported_method_for_api == "update" else "get" if supported_method_for_api == "list" or supported_method_for_api == "retrieve" else supported_method_for_api

            http_request = HttpRequest()
            http_request.method = supported_method_for_api
            http_request.META = {"HTTP_USER_AGENT": "Mozilla/5.0"}
            http_request.url = full_url
            http_request.query_params = {}
            http_request.data = {}
            model_obj = None
            model_name = ""
            view_class = test_case_api_class.callback.view_class()
            view_class.request = http_request
            try:
                if hasattr(view_class.get_serializer_class(), "Meta"):
                    model_obj = view_class.get_serializer_class().Meta.model
                elif isinstance(view_class.get_queryset(), QuerySet):
                    model_obj = view_class.get_queryset().model

                if model_obj:
                    model_name = model_obj.__name__
            except AssertionError:
                pass

            # if tests.py not exists, then we need to create an empty tests.py file.
            if not os.path.isfile(test_file_dir):
                with open(test_file_dir, "w"):
                    pass

            # reading the content of the file and creating tree using ast module.
            with open(test_file_dir, "r") as file:
                # Read the content of the file
                file_content = file.read()
            tree = ast.parse(file_content)

            # add test case import statement if not exist in the file
            self.add_test_case_import_statement(tree, test_file_dir)

            classes = [
                node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]

            if test_case_name_upper_case not in classes:
                # creating class node.
                supported_methods_string = ",".join(supported_methods)
                class_comment = ast.Expr(
                    value=ast.Constant(
                        value=f"Writing a {supported_methods_string} method test case for {test_case_name_lower_case}",
                    ),
                )
                class_node = ast.ClassDef(
                    name=test_case_name_upper_case,
                    bases=[ast.Name(id=self.base_test_class_name, ctx=ast.Load())],
                    body=[class_comment],
                    decorator_list=[],
                    keywords=[],
                    lineno=2,
                    col_offset=0,
                )

                # setup method creation.
                method_setup_node = self.setup_method(reverse_url_name, tree, test_file_dir, is_auth_required, model_name, model_obj)
                class_node.body.append(method_setup_node)

                for supported_method in supported_methods:
                    if supported_method == "list":
                        method_node_list = self.get_method_test_case(test_case_name_lower_case, is_auth_required)
                        for method_node in method_node_list:
                            class_node.body.append(method_node)
                    if supported_method == "create":
                        method_node_list = self.create_method_test_case(test_case_name_lower_case, is_auth_required, model_obj)
                        for method_node in method_node_list:
                            class_node.body.append(method_node)
                    if supported_method == "update":
                        method_node_list = self.update_method_test_case(test_case_name_lower_case, is_auth_required)
                        for method_node in method_node_list:
                            class_node.body.append(method_node)
                    if supported_method == "retrieve":
                        method_node_list = self.retrieve_method_test_case(test_case_name_lower_case, is_auth_required)
                        for method_node in method_node_list:
                            class_node.body.append(method_node)
                    if supported_method == "destroy":
                        method_node_list = self.destroy_method_test_case(test_case_name_lower_case, is_auth_required)
                        for method_node in method_node_list:
                            class_node.body.append(method_node)

                print(f"URL: {api_name}, Test cases created")

                # combining class and method node and write on the file.
                tree.body.append(class_node)
                generated_code = astor.to_source(tree)
                with open(test_file_dir, "w") as file:
                    file.write(generated_code)
