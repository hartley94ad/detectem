import re
import inspect
import logging
import glob

from importlib.util import find_spec, module_from_spec

from zope.interface import implementer, Interface, Attribute
from zope.interface.verify import verifyObject
from zope.interface.exceptions import BrokenImplementation

logger = logging.getLogger('detectem')


def get_plugin_by_name(name, plugins):
    try:
        return [p for p in plugins if p.name == name][0]
    except IndexError:
        return None


class _PluginLoader(object):

    def __init__(self):
        self.plugins = []

    def _full_class_name(self, ins):
        return '{}.{}'.format(ins.__class__.__module__, ins.__class__.__name__)

    def _get_plugin_module_paths(self, plugin_dir):
        filepaths = [
            fp for fp in glob.glob('{}/**/*.py'.format(plugin_dir), recursive=True)
            if not fp.endswith('__init__.py')
        ]
        rel_paths = [re.sub(plugin_dir.rstrip('/') + '/', '', fp) for fp in filepaths]
        module_paths = [rp.replace('/', '.').replace('.py', '') for rp in rel_paths]
        return module_paths

    def _load_plugin(self, klass):
        ins = klass()
        try:
            if verifyObject(IPlugin, ins):
                self.plugins.append(ins)
        except BrokenImplementation:
            logger.warning(
                "Plugin '%(name)s' doesn't provide the plugin interface",
                {'name': self._full_class_name(ins)}
            )

    def load_plugins(self, plugins_package):
        # Resolve directory in the filesystem
        plugin_dir = find_spec(plugins_package).submodule_search_locations[0]

        for module_path in self._get_plugin_module_paths(plugin_dir):
            # Load the module dynamically
            spec = find_spec('{}.{}'.format(plugins_package, module_path))
            m = module_from_spec(spec)
            spec.loader.exec_module(m)

            # Get classes from module and extract the plugin classes
            classes = inspect.getmembers(m, predicate=inspect.isclass)
            for _, klass in classes:
                if klass.__module__ != spec.name:
                    continue
                if not klass.__name__.endswith('Plugin'):
                    continue
                self._load_plugin(klass)


def load_plugins():
    """ Return the list of plugin instances """
    loader = _PluginLoader()
    loader.load_plugins('detectem.plugins')
    return loader.plugins


class IPlugin(Interface):
    name = Attribute(""" Name to identify the plugin. """)
    homepage = Attribute(""" Plugin homepage. """)


@implementer(IPlugin)
class Plugin():
    def _get_matchers(self, value, source='matchers'):
        matchers_dict = getattr(self, source, [])
        return [m[value] for m in matchers_dict if value in m]

    def get_grouped_matchers(self, source='matchers'):
        """ Return dictionary of matchers (not empty ones) """
        data = {}
        for k in ['url', 'body', 'header']:
            m = self._get_matchers(k, source)
            if m:
                data[k] = m

        return data

    @property
    def is_modular(self):
        return bool(hasattr(self, 'modular_matchers'))

    @property
    def is_indicator(self):
        return bool(hasattr(self, 'indicators'))
