import errno
import json
import logging
import os
import sys

LOGGER = logging.getLogger(__name__)


class Whitelist(object):

    def __init__(self, config):
        self.__loadedconfig = config
        self.__admins = self.__loadedconfig.get('LIST_OF_ADMINS', [])
        self.__filename = "whitelist.json"

        self.__whitelist_enabled = len(self.__admins) > 0
        self.__whitelist = []
        if self.__whitelist_enabled:
            LOGGER.info('Whitelist enabled.')
            self.__load_whitelist()
        else:
            LOGGER.info('Whitelist disabled. No admins configured.')

    def is_whitelist_enabled(self):
        return self.__whitelist_enabled

    def is_admin(self, user_name):
        return not self.is_whitelist_enabled() or (user_name in self.__admins)

    def is_whitelisted(self, user_name):
        return self.is_admin(user_name) or (user_name in self.__whitelist)

    def add_user(self, user_name):
        if self.is_whitelist_enabled() and (user_name not in self.__whitelist):
            LOGGER.info('Adding <%s> to whitelist.' % (user_name))
            self.__whitelist.append(user_name)
            self.__save_whitelist()
            return True
        return False

    def rem_user(self, user_name):
        if self.is_whitelist_enabled() and (user_name in self.__whitelist):
            LOGGER.info('Removing <%s> from whitelist.' % (user_name))
            self.__whitelist.remove(user_name)
            self.__save_whitelist()
            return True
        return False

    @staticmethod
    def __get_default_dir():
        directory = os.path.join(os.path.dirname(sys.argv[0]), "serverdata")
        try:
            os.makedirs(directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                LOGGER.error('Unable to create serverdata directory.')
        return directory

    def __load_whitelist(self):
        fullpath = os.path.join(self.__get_default_dir(), self.__filename)

        LOGGER.info('Whitelist loading.')
        self.__whitelist = []
        if os.path.isfile(fullpath):
            try:
                with open(fullpath, 'r', encoding='utf-8') as f:
                    self.__whitelist = json.load(f)
                LOGGER.info('Whitelist loaded successful.')
            except Exception as e:
                LOGGER.error(e)
        else:
            LOGGER.warning('No whitelist file present.')
            self.__whitelist = []

    def __save_whitelist(self):
        fullpath = os.path.join(self.__get_default_dir(), self.__filename)

        LOGGER.info('Whitelist saving.')
        try:
            with open(fullpath, 'w', encoding='utf-8') as file:
                json.dump(self.__whitelist, file, indent=4, sort_keys=True, separators=(',', ':'))
            LOGGER.info('Whitelist saved successful.')
        except Exception as e:
            LOGGER.warning('Error while saving whitelist. (%s)' % (e))
