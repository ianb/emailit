from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='EmailIt',
      version=version,
      description="Email web pages",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='email web html wsgi application',
      author='Ian Bicking',
      author_email='ianb@openplans.org',
      url='',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
        'WebOb',
        'Paste',
        'Tempita',
        'lxml>=2.0alpha',
        # PasteScript?
      ],
      entry_points="""
      [paste.app_factory]
      main = emailit.wsgiapp:make_app
      """,
      )
