from setuptools import setup, find_packages


setup(
    name="tdjango",
    version='0.0.4',
    url='http://github.com/calston/tdjango',
    license='MIT',
    description="A Twisted interface to the Django ORM",
    author='Colin Alston',
    author_email='colin.alston@gmail.com',
    packages=find_packages(),
    install_requires=[
        'Twisted',
        'Django',
        'psycopg2',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
    ],
)
