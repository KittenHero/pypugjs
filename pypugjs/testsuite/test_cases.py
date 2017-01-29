from __future__ import print_function
import pypugjs
import pypugjs.ext.html
from pypugjs.utils import process
from pypugjs.exceptions import CurrentlyNotSupported
import six

from nose import with_setup

processors =  {}
jinja_env = None

def teardown_func():
    pass


try:
    from jinja2 import Environment, FileSystemLoader
    from pypugjs.ext.jinja import PyPugJSExtension
    jinja_env = Environment(extensions=[PyPugJSExtension], loader=FileSystemLoader('cases/'))
    def jinja_process (src, filename):
        global jinja_env
        template = jinja_env.get_template(filename)
        return template.render()

    processors['Jinja2'] = jinja_process
except ImportError:
    pass

# Test jinja2 with custom variable syntax: "{%#.-.** variable **.-.#%}"
try:
    from jinja2 import Environment, FileSystemLoader
    from pypugjs.ext.jinja import PyPugJSExtension
    jinja_env = Environment(extensions=[PyPugJSExtension], loader=FileSystemLoader('cases/'),
			variable_start_string = "{%#.-.**", variable_end_string="**.-.#%}"
    )
    def jinja_process_variable_start_string (src, filename):
        global jinja_env
        template = jinja_env.get_template(filename)
        return template.render()

    processors['Jinja2-variable_start_string'] = jinja_process_variable_start_string
except ImportError:
    pass

try:
    import tornado.template
    from pypugjs.ext.tornado import patch_tornado
    patch_tornado()

    loader = tornado.template.Loader('cases/')
    def tornado_process (src, filename):
        global loader, tornado
        template = tornado.template.Template(src,name='_.pug',loader=loader)
        generated = template.generate(missing=None)
        if isinstance(generated, six.binary_type):
            generated = generated.decode("utf-8")
        return generated

    processors['Tornado'] = tornado_process
except ImportError:
    pass

try:
    import django
    from django.conf import settings
    if django.VERSION >= (1, 8, 0):
        config = {
            'TEMPLATES': [{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': ["cases/"],
                'OPTIONS': {
                    'context_processors': [
                        'django.template.context_processors.debug',
                        'django.template.context_processors.request',
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages',
                        'django.core.context_processors.request'
                    ],
                    'loaders': [
                        ('pypugjs.ext.django.Loader', (
                            'django.template.loaders.filesystem.Loader',
                            'django.template.loaders.app_directories.Loader',
                        ))
                    ],
                },
            }]
        }
        if django.VERSION >= (1, 9, 0):
            config['TEMPLATES'][0]['OPTIONS']['builtins'] = ['pypugjs.ext.django.templatetags']
    else:
        config = {
            'TEMPLATE_DIRS': ("cases/",),
            'TEMPLATE_LOADERS': (
                ('pypugjs.ext.django.Loader', (
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                )),
            )
        }

    settings.configure(**config)

    if django.VERSION >= (1, 7, 0):
        django.setup()

    import django.template
    import django.template.loader
    from pypugjs.ext.django import Compiler as DjangoCompiler

    def django_process(src, filename):
        compiled = process(src, filename=filename, compiler=DjangoCompiler)
        print(compiled)
        t = django.template.Template(compiled)

        ctx = django.template.Context()
        return t.render(ctx)

    processors['Django'] = django_process
except ImportError:
    raise

try:
    import pypugjs.ext.mako
    import mako.template
    from mako.lookup import TemplateLookup
    dirlookup = TemplateLookup(directories=['cases/'],preprocessor=pypugjs.ext.mako.preprocessor)

    def mako_process(src, filename):
        t = mako.template.Template(src, lookup=dirlookup,preprocessor=pypugjs.ext.mako.preprocessor, default_filters=['decode.utf8'])
        return t.render()

    processors['Mako'] = mako_process

except ImportError:
    pass

def setup_func():
    global jinja_env, processors

def html_process(src, filename):
    # hack for includes to work because of working directory
    if 'include' in src:
        import re
        src = re.sub(r'((^|\n)\s*include )(?!cases/)', '\\1cases/', src)
    return pypugjs.ext.html.process_pugjs(src)

processors['Html'] = html_process

def run_case(case,process):
    import codecs
    global processors
    processor = processors[process]
    with codecs.open('cases/%s.pug'%case, encoding='utf-8') as pugjs_file:
        pugjs_src = pugjs_file.read()
        if isinstance(pugjs_src, six.binary_type):
            pugjs_src = pugjs_src.decode('utf-8')
        pugjs_file.close()

    with codecs.open('cases/%s.html'%case, encoding='utf-8') as html_file:
        html_src = html_file.read().strip('\n')
        if isinstance(html_src, six.binary_type):
            html_src = html_src.decode('utf-8')
        html_file.close()
    try:
        processed_pugjs = processor(pugjs_src, '%s.pug'%case).strip('\n')
        print('PROCESSED\n',processed_pugjs,len(processed_pugjs))
        print('EXPECTED\n',html_src,len(html_src))
        assert processed_pugjs==html_src

    except CurrentlyNotSupported:
        pass

exclusions = {
    'Html': set(['mixins', 'mixin.blocks', 'layout', 'unicode']),
    'Mako': set(['layout']),
    'Tornado': set(['layout']),
    'Jinja2': set(['layout']),
    'Jinja2-variable_start_string': set(['layout']),
    'Django': set(['layout'])}


@with_setup(setup_func, teardown_func)
def test_case_generator():
    global processors

    import os
    import sys
    for dirname, dirnames, filenames in os.walk('cases/'):
        # raise Exception(filenames)
        filenames = filter(lambda x:x.endswith('.pug'),filenames)
        filenames = list(map(lambda x:x.replace('.pug',''),filenames))
        for processor in processors.keys():
            for filename in filenames:
                if not filename in exclusions[processor]:
                    yield run_case, filename,processor