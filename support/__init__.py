
from .utils import DateContext
from .metadata_manager import Store as MetaDataManager
from .data_manager import LoadConfig, load_data
from .reporter import (create_budget, create_expense_report, describe_analysis,
    generate_report, plot_dashboard, data_validation, SavePaths)

class DataManager:
    cfg = staticmethod(LoadConfig)
    load = staticmethod(load_data)

class Reporter:
    describe = staticmethod(describe_analysis)
    budget = staticmethod(create_budget)
    expense = staticmethod(create_expense_report)
    report = staticmethod(generate_report)
    dashboard = staticmethod(plot_dashboard)
    validate = staticmethod(data_validation)


# print("Le utilià di supporto sono state importate!")