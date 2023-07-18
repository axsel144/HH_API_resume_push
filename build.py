from distutils.core import setup
import py2exe

setup(
    name='ResumePusher',
    description="Script to autopush your resume",
    version="0.1",

    console=[{'script': 'main.py'}],
    options={'py2exe': {
        'packages': 'encodings, pubsub',
        'includes': None}
    },
)
