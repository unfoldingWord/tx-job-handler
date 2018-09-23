from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, func

from general_tools.data_utils import convert_string_to_date
from models.tx_model import TxModel
from models.text_pickle_type import TextPickleType
from global_settings.global_settings import GlobalSettings


class TxModule(GlobalSettings.Base, TxModel):
    __tablename__ = GlobalSettings.module_table_name
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(100), nullable=False)
    version = Column(String(100), nullable=False)
    input_format = Column(TextPickleType, nullable=False)
    output_format = Column(TextPickleType, nullable=False)
    resource_types = Column(TextPickleType, nullable=False)
    options = Column(TextPickleType, default=[], nullable=False)
    public_links = Column(TextPickleType, default=[], nullable=False)
    private_links = Column(TextPickleType, default=[], nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        """Init attributes"""
        self.resource_types = []
        self.input_format = []
        self.output_format = []
        self.options = []
        self.private_links = []
        self.public_links = []
        self.resource_types = []
        self.version = '1'
        super(TxModule, self).__init__(**kwargs)
        self.created_at = convert_string_to_date(self.created_at)
        self.updated_at = convert_string_to_date(self.updated_at)
