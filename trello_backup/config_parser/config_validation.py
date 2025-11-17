import json
from abc import ABC, abstractmethod
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Set, Any, Optional, re, List, Dict

from pythoncommons.string_utils import auto_str

from trello_backup.exception import TrelloConfigException

LOG = logging.getLogger(__name__)


class ConfigSource(Enum):
    MAIN = ("main config", set())
    SECRETS = ("secrets config", set())

    def __init__(self, val, excluded_fields_emptiness_check: Set[str]):
        self.val = val
        self.excluded_fields_emptiness_check = excluded_fields_emptiness_check if excluded_fields_emptiness_check else set()


class ValidationErrorType(Enum):
    UNDEFINED_CONFIG = ("undefined_config", "Undefined configs")
    INVALID_CONFIG_VALUE = ("invalid_config_type", "Invalid config value")

    def __init__(self, val, human_readable_err):
        self.val = val
        self.human_readable_err = human_readable_err


@dataclass(frozen=True)
class ValidationContext:
    conf_source: ConfigSource
    conf_file: str



class ValidationErrorAbs(ABC):
    def __init__(self, type: ValidationErrorType, message: str):
        self.type = type
        self.message = message

    @abstractmethod
    def to_short_str(self):
        pass

    @staticmethod
    def create_invalid_config_value(message, cfg, value, additional_message=None):
        additional_info = f"config: {cfg}, value: {value}"
        if additional_message:
            additional_info += f", additional message: {additional_message}"
        return WorkflowConfigValidationError(ValidationErrorType.INVALID_CONFIG_VALUE,
                                             message, ctx_path=None, additional_info=additional_info)

    @staticmethod
    def create_undefined_config_error(message, ctx_path, cfg, value):
        return MissingConfigValidationError(ValidationErrorType.UNDEFINED_CONFIG, message, ctx_path, cfg, value)



@auto_str
class ConfigValidationError(ValidationErrorAbs):
    def __init__(self, type: ValidationErrorType, message,
                 obj_path=None, field_name=None, field_value=None, var_name=None):
        super().__init__(type, message)
        self.obj_path = obj_path
        self.field_name = field_name
        self.field_value = field_value
        self.var_name = var_name
        self.src = None
        self.short_matched_field_value = self._get_short_match(field_value, var_name)

    @staticmethod
    def _get_short_match(field_value, var_name):
        if not field_value:
            return field_value
        if "\n" in field_value:
            matches = re.findall(r".*\$\{" + var_name + "}.*", field_value)
            match = matches[0]
            return match
        return field_value

    def to_short_str(self):
        if self.var_name:
            return f"Var: {self.var_name}, path: {self.obj_path}, value: {self.short_matched_field_value}"
        else:
            return f"Field: {self.field_name}, path: {self.obj_path}, value: {self.short_matched_field_value}"


@auto_str
class MissingConfigValidationError(ValidationErrorAbs):
    def __init__(self, type: ValidationErrorType, message, ctx_path, cfg, value):
        super().__init__(type, message)
        self.ctx_path = ctx_path
        self.cfg = cfg
        self.value = value

    def to_short_str(self):
        return f"Context path: {self.ctx_path}\nconfig: {self.cfg}, value: {self.value}"



@auto_str
class WorkflowConfigValidationError(ValidationErrorAbs):
    def __init__(self, type: ValidationErrorType, message: str, ctx_path: Optional[str], additional_info: Any):
        super().__init__(type, message)
        self.ctx_path = ctx_path
        self.additional_info = additional_info

    def to_short_str(self):
        return f"Message: {self.message}, Context path: {self.ctx_path}, additional_info: {self.additional_info}"


@auto_str
class ConfigValidator:
    def __init__(self):
        self._errors: Dict[ValidationContext, List[ValidationErrorAbs]] = defaultdict(list)
        self._field_values: Set[str] = set()
        self._new_errors: List[str] = []
        self._context: ValidationContext = None

    def set_context(self, ctx: ValidationContext):
        self._context = ctx

    @property
    def config_type(self):
        return self._context.conf_source

    @property
    def excluded_fields_emptiness_check(self):
        return self._context.conf_source.excluded_fields_emptiness_check

    def report_error(self, error: ValidationErrorAbs):
        LOG.error("Validation error reported: %s", error)
        error.src = self._context
        self._errors[self._context].append(error)
        if hasattr(error, "field_value"):
            self._field_values.add(error.field_value)

    def check_if_already_reported(self, message: str, field_value: str):
        if field_value not in self._field_values:
            LOG.warning("The following unresolved variable was not reported during normal execution. "
                        "Message: %s, field value: %s", message, field_value)
            self._new_errors.append(message)

    def fail_if_errors(self):
        errors: Dict[ValidationErrorType, Dict[str, List]] = {et: self._filter_by_type(et) for et in ValidationErrorType}
        tmp = [True if errs else False for errs in errors.values()]
        not_empty_errs = sum(bool(x) for x in tmp)

        err_msg = ""
        if not_empty_errs > 1:
            err_msg = "Multiple error types found!\n\n"
        for err_type, errs in errors.items():
            if len(errs) > 0:
                # TODO Does not format newlines well from 'errs'
                err_msg += (f"{err_type.human_readable_err}\n"
                            f"{json.dumps(errs, indent=4)}\n")
        if err_msg:
            raise TrelloConfigException(err_msg)

    def _filter_by_type(self, t: ValidationErrorType) -> Dict[str, List[ConfigValidationError]]:
        result = defaultdict(list)
        for ctx, errors in self._errors.items():
            for err in errors:
                if err.type == t:
                    result[ctx.conf_source.val].append(err.to_short_str())
        return result
