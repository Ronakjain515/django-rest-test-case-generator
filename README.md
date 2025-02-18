# TestCaseGenerator for Django REST APIs
`django_rest_test_case_generator` is a Python library that helps developers automatically generate test cases for their 
Django REST Framework APIs. It crawls through the project, detects class-based views (CBVs), and creates 
corresponding test cases based on the HTTP methods (GET, POST, PUT, DELETE, etc.) defined in those views. 
This saves developers time and ensures that their API endpoints are well-covered by automated tests.

## Getting Started
These instructions will help you to set up the library on your working project and start generating test cases
for development and testing purposes.

### Prerequisites
Before you can use `django_rest_test_case_generator`, you'll need to have the following installed:

```
pip install django djangorestframework
django-admin startproject myproject
cd myproject
```

### Installation

Now, you can install this package.

```
pip install django-rest-test-case-generator
```

In your Django project, add the `test_case_generator_command` app to your `INSTALLED_APPS` in settings.py:

```
INSTALLED_APPS = [
    # Other apps
    'test_case_generator_command',
]
```

Now you're ready to generate test cases for your APIs. Use the following management command to crawl through your project and create the test cases:

```
python manage.py generate_test_case
```
This will scan for class-based views (CBVs) and generate corresponding test cases for each API method (GET, POST, PUT, DELETE).
