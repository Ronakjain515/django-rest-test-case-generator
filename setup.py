from setuptools import find_packages, setup


with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

setup(
    name = "django_rest_test_case_generator",
    version = "0.1.0",
    author = "Ronak Jain",
    author_email = "jronak515@gmail.com",
    description = "Django command to generate test case for rest apis.",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/Ronakjain515/django-rest-test-case-generator",
    project_urls = {
        "Bug Tracker": "https://github.com/Ronakjain515/django-rest-test-case-generator/issues",
    },
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    license="MIT",
    packages=find_packages(include=["test_case_generator_command", "test_case_generator_command.*"]),
    install_requires=[
          'faker',
          'astor',
      ],
    python_requires = ">=3.6",
    keywords='django, test case generator, rest apis, testing',
)
