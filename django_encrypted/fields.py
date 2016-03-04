import pickle
from django.core import checks, exceptions
from django.db import models
from django.utils import six

from .fernet import Fernet


class EncryptedField(models.Field):
    # FIXME: `base_field` has issues with date/time fields
    def __init__(self, base_field, **kwargs):
        """
        :type base_field: django.db.models.fields.Field
        :rtype: None
        """
        self._fernet = Fernet()
        self.base_field = base_field
        # self.field = base_field(*args, **kwargs)
        super(EncryptedField, self).__init__(**kwargs)

    def __getattr__(self, item):
        # Map back to base_field instance
        return getattr(self.base_field, item)

    def check(self, **kwargs):
        errors = super(EncryptedField, self).check(**kwargs)
        if self.base_field.rel:
            errors.append(
                checks.Error(
                    'Base field for encrypted cannot be a related field.',
                    hint=None,
                    obj=self,
                    id='encrypted.E002'
                )
            )
        else:
            # Remove the field name checks as they are not needed here.
            base_errors = self.base_field.check()
            if base_errors:
                messages = '\n    '.join('%s (%s)' % (error.msg, error.id) for error in base_errors)
                errors.append(
                    checks.Error(
                        'Base field for encrypted has errors:\n    %s' % messages,
                        hint=None,
                        obj=self,
                        id='encrypted.E001'
                    )
                )
        return errors

    def set_attributes_from_name(self, name):
        super(EncryptedField, self).set_attributes_from_name(name)
        self.base_field.set_attributes_from_name(name)

    @property
    def description(self):
        return 'Encrypted %s' % self.base_field.description

    def get_internal_type(self):
        return "BinaryField"

    def deconstruct(self):
        name, path, args, kwargs = super(EncryptedField, self).deconstruct()
        kwargs.update({
            'base_field': self.base_field,
        })
        return name, path, args, kwargs

    def get_db_prep_value(self, value, connection, prepared=False):
        value = self.base_field.get_db_prep_value(value, connection, prepared)
        if value is None:
            return value

        return self._fernet.encrypt(pickle.dumps(value))

    def from_db_value(self, value, expression, connection, context):
        return pickle.loads(self._fernet.decrypt(value)) if value else value

    def validate(self, value, model_instance):
        super(EncryptedField, self).validate(value, model_instance)
        self.base_field.validate(value, model_instance)

    def run_validators(self, value):
        super(EncryptedField, self).run_validators(value)
        self.base_field.run_validators(value)
