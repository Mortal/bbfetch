import os
from setuptools import find_packages, setup

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.dirname(os.path.abspath(__file__))))

# with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
#     README = readme.read()

setup(
    name='bbfetch',
    version='0.3a1',
    packages=find_packages(include=['bbfetch', 'bbfetch.*']),
    include_package_data=True,
    license='GNU GPLv3',
    description='Command-line interface to Blackboard LMS',
    long_description='Command-line interface to Blackboard LMS',
    url='https://github.com/Mortal/bbfetch',
    author='Mathias Rav',
    author_email='rav@cs.au.dk',
    install_requires=[
        'html2text',
        'keyring',
        'requests',
        'six',
        'html5lib==0.999999999',
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
)
