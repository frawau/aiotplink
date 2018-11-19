#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from distutils.core import setup

version = '0.1.0'
package = 'aiotplink'

setup(name=package,
    packages=[package],
    version=version,
    author='François Wautier',
    author_email='francois@wautier.eu',
    description='API for local communication with TP-Link Smart Plugs devices over a LAN with asyncio.',
    url='http://github.com/frawau/'+package,
    download_url='https://github.com/frawau/'+package+'/archive/'+version+'.tar.gz',
    keywords = ['TP-Link', 'IoT', 'switch', 'Smart Plug', 'automation'],
    license='MIT',
    install_requires=[
    ],
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5'
    ])
