from datetime import datetime, date

from sqlalchemy import inspect

from global_settings.global_settings import GlobalSettings


class TxModel(object):

    def __init__(self, **kwargs):
        pass

    def insert(self):
        GlobalSettings.db().add(self)
        GlobalSettings.db().commit()
        GlobalSettings.db().close()

    def update(self):
        GlobalSettings.db().merge(self)
        GlobalSettings.db().commit()
        GlobalSettings.db().close()

    def delete(self):
        GlobalSettings.db().delete(self)
        GlobalSettings.db().commit()
        GlobalSettings.db().close()

    @classmethod
    def get(cls, *args, **kwargs):
        """
        :param args:
        :param kwargs:
        :return TxModel:
        """
        if args:
            kwargs[inspect(cls).primary_key[0].name] = args[0]
        item = cls.query(**kwargs).first()
        GlobalSettings.db().close()
        return item

    @classmethod
    def query(cls, **kwargs):
        items = GlobalSettings.db().query(cls).filter_by(**kwargs)
        return items

    def __iter__(self):
        for c in inspect(self).mapper.column_attrs:
            value = getattr(self, c.key)
            if isinstance(value, (datetime, date)):
                value = value.strftime("%Y-%m-%dT%H:%M:%SZ")
            yield (c.key, value)

    def clone(self):
        return self.__class__(**dict(self))
