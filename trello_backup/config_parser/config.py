import dataclasses
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Callable, Optional, List, Iterable

from pythoncommons.file_utils import FileUtils, JsonFileUtils

from trello_backup.config_parser.config_validation import ValidationErrorAbs, ValidationContext, ConfigSource, ConfigValidator
from trello_backup.constants import FilePath
from trello_backup.exception import TrelloConfigException

import logging

from trello_backup.utils import ObjectUtils

LOG = logging.getLogger(__name__)


class TypeChecker(Enum):
    LIST_STR = (ObjectUtils.type_check_list_str, List[str])
    STR = (ObjectUtils.type_check_lenient_str, str)
    BOOL = (ObjectUtils.type_check_strict_bool, bool)
    DATE = (ObjectUtils.type_check_date, str)

    def __init__(self, checker_func: Callable, typing):
        self.checker_func = checker_func
        self.typing = typing

    def do_type_check(self, value):
        return self.checker_func(value)

    def __str__(self):
        return f"{{checker_func: {self.checker_func.__name__}, required type: {self.typing} }}"



class TrelloConfigType(Enum):
    GLOBAL = ("global", "Global config")
    SECRET = ("secret", "Secrets config")

    def __init__(self, value, human_readable_name):
        self.val = value
        self.human_readable_name = human_readable_name

    @staticmethod
    def by_value(val):
        for ct in TrelloConfigType:
            if ct.val == val:
                return ct
        raise TrelloConfigException(f"Enum with value '{val}' not found!")


class TrelloConfigCategory(Enum):
    GENERIC = "generic"
    SECRET = "secret"


class TrelloCfg(Enum):
    __BY_KEY__ = None

    ########################################
    # Secret configs
    TRELLO_API_KEY = (TrelloConfigType.SECRET, TrelloConfigCategory.SECRET, "api_key", TypeChecker.STR)
    TRELLO_TOKEN = (TrelloConfigType.SECRET, TrelloConfigCategory.SECRET, "token", TypeChecker.STR)
    TRELLO_SECRET = (TrelloConfigType.SECRET, TrelloConfigCategory.SECRET, "secret", TypeChecker.STR)

    ########################################
    # Global configs
    SERVE_ATTACHMENTS =  (TrelloConfigType.GLOBAL, TrelloConfigCategory.GENERIC, "serve_attachments", TypeChecker.BOOL)

    def __init__(self, type, category, key, type_checker, value_checker=None, defaults: Dict[str, str] = None):
        self.type = type
        self.category = category
        self.key = key
        self.type_checker = type_checker
        self.value_checker = value_checker
        self.defaults = defaults

    def get_default(self, env):
        return self.defaults[env]

    @staticmethod
    def global_configs():
        return TrelloCfg._filter_by_cfg_type(TrelloConfigType.GLOBAL)

    @staticmethod
    def secret_configs():
        return TrelloCfg._filter_by_cfg_type(TrelloConfigType.SECRET)

    @staticmethod
    def _filter_by_cfg_type(cfg_type):
        result = []
        for cfg in TrelloCfg:
            if cfg.type == cfg_type:
                result.append(cfg)
        return result

    @classmethod
    def lookup_by_key(cls, key: str):
        if not cls.__BY_KEY__:
            cls.__BY_KEY__ = {cfg.key: cfg for cfg in TrelloCfg}
        if key not in cls.__BY_KEY__:
            raise TrelloConfigException("Unknown configuration key: {}".format(key))
        return cls.__BY_KEY__[key]


class CfgValidator:
    @staticmethod
    def validate_type_and_value(cfg, value, validator):
        validated_value = None
        if cfg:
            try:
                validated_value = cfg.type_checker.do_type_check(value)
            except ValueError:
                validator.report_error(ValidationErrorAbs.create_invalid_config_value(
                    f"Invalid config value for config: {cfg}, type check failed", cfg, value))
            try:
                if cfg.value_checker:
                    cfg.value_checker.check(value)
            except ValueError as e:
                validator.report_error(ValidationErrorAbs.create_invalid_config_value(
                    f"Invalid config value for config: {cfg}, value check failed", cfg, value,
                    additional_message=str(e)))
        return validated_value



@dataclass
class Config:
    _configs: Dict[TrelloCfg, Any] = dataclasses.field(default_factory=dict)

    def __init__(self, main_conf: Dict[str, Any], validator):
        unified_dict = main_conf | dict()  # Add more dicts here if required
        self._configs = self._read_configs(unified_dict, validator)
        ValidationHelpers.validate_configs(validator,
                               required={TrelloCfg.SERVE_ATTACHMENTS},
                               actual=set(self._configs.keys()))

    def get(self, cfg: Any):
        if cfg not in self._configs:
            raise TrelloConfigException(f"Undefined config: {cfg}")
        return self._configs[cfg]

    def get_global_confs(self):
        return {k: v for k, v in self._configs.items() if k.type == TrelloConfigType.GLOBAL}

    def get_configs_as_keys_values(self):
        d = {}
        for cfg, val in self._configs.items():
            d[cfg.key] = val
        return d

    @staticmethod
    def _read_configs(dic, validator):
        result: Dict[TrelloCfg, str] = {}
        for key, value in dic.items():
            cfg = None
            try:
                cfg = TrelloCfg.lookup_by_key(key)
            except TrelloConfigException:
                LOG.warning("No such TrelloCfg, unknown data found in main config. Key: %s. ", key)
            result[cfg] = CfgValidator.validate_type_and_value(cfg, value, validator)
        return result

    def _get_config(self, cfg: TrelloCfg):
        return self._configs[cfg]

    @staticmethod
    def _validate_configs(validator, required, actual):
        if not set(required).issubset(actual):
            not_found_confs = set(required).difference(actual)
            for cfg in not_found_confs:
                validator.report_error(
                    ValidationErrorAbs.create_undefined_config_error(f"Undefined value for config: {cfg}", None, cfg, None))
        return actual


class Secrets:
    def __init__(self, dic: Dict[str, Any], validator):
        self._configs: Dict[TrelloCfg, str] = self._read_configs(dic, validator)
        ValidationHelpers.validate_configs(validator,
                                           required={TrelloCfg.TRELLO_TOKEN, TrelloCfg.TRELLO_SECRET, TrelloCfg.TRELLO_API_KEY},
                                           actual=set(self._configs.keys()))

    @staticmethod
    def _read_configs(dic, validator):
        result: Dict[TrelloCfg, str] = {}
        for key, value in dic.items():
            cfg = None
            try:
                cfg = TrelloCfg.lookup_by_key(key)
            except TrelloConfigException:
                LOG.warning("No such TrelloCfg, unknown data found in secret config. Key: %s. ", key)

            if cfg:
                try:
                    result[cfg] = cfg.type_checker.do_type_check(value)
                except ValueError:
                    validator.report_error(ValidationErrorAbs.create_invalid_config_value(
                        f"Invalid config value for config: {cfg}, type check failed", cfg, value))
        return result

    def get(self, cfg: Any):
        if cfg not in self._configs:
            raise TrelloConfigException(f"Undefined config: {cfg}")
        return self._configs[cfg]

    def get_all(self):
        return self._configs


class ConfigReader:
    def __init__(self):
        self._conf_dir = FilePath.CONFIG_DIR

    @property
    def config(self):
        return f"{self._conf_dir}/config.json"

    @property
    def secrets(self):
        return f"{self._conf_dir}/secrets.json"

    @staticmethod
    def _read(filename):
        LOG.info("Reading config from file: %s", filename)
        if not os.path.exists(filename):
            raise TrelloConfigException(f"Cannot find config file: {filename}")

        with open(filename, "r") as f:
            return f.read()


    def read_config(self, validator) -> Config:
        conf: Config = Config(ConfigReader._read_json_config(self.config), validator)
        return conf

    def read_secrets(self, validator):
        return Secrets(ConfigReader._read_json_config(self.secrets), validator)

    @staticmethod
    def _read_json_config(filename):
        LOG.info("Reading config from file: %s", filename)
        if not os.path.exists(filename):
            raise TrelloConfigException(f"Cannot find config file: {filename}")
        json_contents, _ = JsonFileUtils.load_data_from_json_file(filename)
        return json_contents



@dataclass
class TrelloConfig:
    config: Config
    secrets: Secrets
    log_files: Iterable[str] = None

    def get(self, cfg: TrelloCfg):
        return self.config.get(cfg)

    def get_secret(self, cfg: TrelloCfg):
        return self.secrets.get(cfg)



class ConfigLoader:
    def __init__(self, config_reader):
        self.config_reader = config_reader

    def load(self, ctx) -> TrelloConfig:
        main_conf_validator = ConfigValidator()
        main_conf_validator.set_context(ValidationContext(ConfigSource.MAIN, self.config_reader.config))
        conf: Config = self._read_config(self.config_reader.read_config,
                                         self.config_reader.config,
                                         main_conf_validator)

        secrets_validator = ConfigValidator()
        secrets_validator.set_context(ValidationContext(ConfigSource.SECRETS, self.config_reader.secrets))
        secrets = self._read_config(self.config_reader.read_secrets, self.config_reader.secrets,  secrets_validator)

        trello_conf = TrelloConfig(conf, secrets)
        ConfigLoader.validate_config(trello_conf, {main_conf_validator, secrets_validator})
        return trello_conf

    @staticmethod
    def validate_config(conf, validators):
        for validator in validators:
            validator.fail_if_errors()

    @staticmethod
    def _read_config(func, src_conf_file, validator, kwargs=None):
        try:
            result = func(validator, **kwargs) if kwargs is not None else func(validator)
        except KeyError as e:
            # print(traceback.format_exc())
            configs_str = ", ".join([str(e) for e in e.args])
            LOG.exception(e)
            raise TrelloConfigException(f"Missing config(s): {configs_str} in config file: {src_conf_file}")
        return result

class ValidationHelpers:
    @staticmethod
    def validate_configs(validator, required, actual):
        if not set(required).issubset(actual):
            not_found_confs = set(required).difference(actual)
            for cfg in not_found_confs:
                validator.report_error(
                    ValidationErrorAbs.create_undefined_config_error(f"Undefined value for config: {cfg}", None, cfg, None))
        return actual