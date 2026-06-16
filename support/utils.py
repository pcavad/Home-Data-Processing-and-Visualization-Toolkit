

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, Field, computed_field
import warnings
warnings.filterwarnings("ignore")

# Date format across the project
from .config import DATE_FMT

#### pydantic ####
class DateContext(BaseModel):
    """
    Generates a comprehensive set of relative dates based on the current time.
    Calculations happen upon instantiation.
    """
    # Primary input - default_factory ensures 'now' is evaluated when called, not at import
    curr_date: datetime = Field(default_factory=datetime.now)

    # We use @property with @computed_field so these are included in .model_dump() 
    # and treated as part of the data schema.

    @property
    def fday(self) -> datetime:
        return self.curr_date.replace(day=1)

    @property
    def first_day_curr_year(self) -> datetime:
        return datetime(self.curr_date.year, 1, 1)

    @property
    def first_day_prev_year(self) -> datetime:
        return datetime(self.curr_date.year - 1, 1, 1)

    @property
    def last_day_prev_month(self) -> datetime:
        return self.fday - timedelta(days=1)

    @property
    def first_day_prev_month(self) -> datetime:
        return self.last_day_prev_month.replace(day=1)

    # --- Computed Variables (Visible in exports) ---

    @computed_field
    @property
    def end_prev_month(self) -> str:
        return self.last_day_prev_month.strftime(DATE_FMT)

    @computed_field
    @property
    def start_curr_month_min1Y(self) -> str:
        return (self.fday - relativedelta(years=1)).strftime(DATE_FMT)

    @computed_field
    @property
    def start_curr_month_min2Y(self) -> str:
        return (self.fday - relativedelta(years=2)).strftime(DATE_FMT)

    @computed_field
    @property
    def end_3months_before(self) -> str:
        return (self.fday - relativedelta(months=3, days=1)).strftime(DATE_FMT)

    # --- Variables used in reporter ---

    @computed_field
    @property
    def start_current_year(self) -> str:
        return self.first_day_curr_year.strftime(DATE_FMT)

    @computed_field
    @property
    def start_previous_year(self) -> str:
        return self.first_day_prev_year.strftime(DATE_FMT)

    @computed_field
    @property
    def start_current_month_minus_one_year(self) -> str:
        return (self.fday - relativedelta(years=1)).strftime(DATE_FMT)

    @computed_field
    @property
    def start_previous_month(self) -> str:
        return self.first_day_prev_month.strftime(DATE_FMT)

    @computed_field
    @property
    def end_previous_month(self) -> str:
        return self.last_day_prev_month.strftime(DATE_FMT)

    @computed_field
    @property
    def end_previous_month_minus_one_year(self) -> str:
        return (self.last_day_prev_month - relativedelta(years=1)).strftime(DATE_FMT)

    @computed_field
    @property
    def previous_month_name(self) -> str:
        return self.first_day_prev_month.strftime("%B")

    @computed_field
    @property
    def current_year_name(self) -> str:
        return self.first_day_prev_month.strftime("%Y")


##### Alternatives using dataclass #####

# from dataclasses import dataclass, field

# @dataclass
# class DateContext:
#     """
#     Generates a comprehensive set of relative dates based on the current time.

#     Note: the math in the class body only runs once. When your script starts, 
#     curr_date is set to that exact second, and all intermediate objects 
#     are calculated immediately and never change again for the duration of the program.

#     To change this behavior, see below alternative implementations using __post_init__.
#     """
#     # Primary input

#     curr_date: datetime = datetime.now()

#     # Intermediate Date Objects for calculations
#     fday: datetime = curr_date.replace(day=1)
#     first_day_curr_year: datetime = datetime(curr_date.year, 1, 1)
#     first_day_prev_year: datetime = datetime(curr_date.year - 1, 1, 1)
#     last_day_prev_month: datetime = fday - timedelta(days=1)
#     first_day_prev_month: datetime = last_day_prev_month.replace(day=1)

#     # --- Variables used in main ---

#     @property
#     def end_prev_month(self):
#         return self.last_day_prev_month.strftime(DATE_FMT)

#     @property
#     def start_curr_month_min1Y(self):
#         return (self.fday - relativedelta(years=1)).strftime(DATE_FMT)

#     @property
#     def start_curr_month_min2Y(self):
#         return (self.fday - relativedelta(years=2)).strftime(DATE_FMT)

#     @property
#     def end_3months_before(self):
#         return (self.fday - relativedelta(months=3, days=1)).strftime(DATE_FMT)

#     # --- Variables used in reporter ---

#     @property
#     def start_current_year(self):
#         return self.first_day_curr_year.strftime(DATE_FMT)

#     @property
#     def start_previous_year(self):
#         return self.first_day_prev_year.strftime(DATE_FMT)

#     @property
#     def start_current_month_minus_one_year(self):
#         return (self.fday - relativedelta(years=1)).strftime(DATE_FMT)

#     @property
#     def start_previous_month(self):
#         return self.first_day_prev_month.strftime(DATE_FMT)

#     @property
#     def end_previous_month(self):
#         return self.last_day_prev_month.strftime(DATE_FMT)

#     @property
#     def end_previous_month_minus_one_year(self):
#         return (self.last_day_prev_month - relativedelta(years=1)).strftime(DATE_FMT)

#     @property
#     def previous_month_name(self):
#         return self.first_day_prev_month.strftime("%B")

#     @property
#     def current_year_name(self):
#         return self.first_day_prev_month.strftime("%Y")

# ----------------
# @dataclass
# class DateContext:
#     """
#     Generates a comprehensive set of relative dates based on the current time.
#     """
#     # 1. Primary input
#     anchor: datetime = field(default_factory=datetime.now, repr=False)
    
#     # 2. Calculated Date Objects (hidden from repr to keep output clean)
#     curr_date: datetime = field(init=False)
    
#     # 3. String Variables (Original set)
#     end_prev_month: str = field(init=False)
#     start_curr_month_min1Y: str = field(init=False)
#     start_curr_month_min2Y: str = field(init=False)
#     end_3months_before: str = field(init=False)
    
#     # 4. String Variables (New descriptive set)
#     start_current_year: str = field(init=False)
#     start_previous_year: str = field(init=False)
#     start_current_month_minus_one_year: str = field(init=False)
#     start_previous_month: str = field(init=False)
#     end_previous_month_minus_one_year: str = field(init=False)
#     previous_month_name: str = field(init=False)
#     current_year_name: str = field(init=False)

#     def __post_init__(self):
#         # Setup base references
#         self.curr_date = self.anchor
#         fday = self.anchor.replace(day=1)
        
#         # Intermediate Date Objects for calculations
#         first_day_curr_year = datetime(self.curr_date.year, 1, 1)
#         first_day_prev_year = datetime(self.curr_date.year - 1, 1, 1)
#         last_day_prev_month = fday - timedelta(days=1)
#         first_day_prev_month = last_day_prev_month.replace(day=1)
        
#         # --- Assignments: variables used in main ---
#         self.end_prev_month = last_day_prev_month.strftime(DATE_FMT)
#         self.start_curr_month_min1Y = (fday - relativedelta(years=1)).strftime(DATE_FMT)
#         self.start_curr_month_min2Y = (fday - relativedelta(years=2)).strftime(DATE_FMT)
#         self.end_3months_before = (fday - relativedelta(months=3, days=1)).strftime(DATE_FMT)

#         # --- Assignments: variables used in reporter ---
#         self.start_current_year = first_day_curr_year.strftime(DATE_FMT)
#         self.start_previous_year = first_day_prev_year.strftime(DATE_FMT)
#         self.start_current_month_minus_one_year = self.start_curr_month_min1Y
#         self.start_previous_month = first_day_prev_month.strftime(DATE_FMT)
#         self.end_previous_month = last_day_prev_month.strftime(DATE_FMT)
#         self.end_previous_month_minus_one_year = (last_day_prev_month - relativedelta(years=1)).strftime(DATE_FMT)
#         self.previous_month_name = first_day_prev_month.strftime("%B")
#         self.current_year_name = first_day_prev_month.strftime("%Y")

##### Alternatives using a class #####

# class DateContext:
#     """
#     Generates relative dates based on a reference 'anchor' date.
#     """
#     def __init__(self, reference_date=None):
#         # Fallback to today if no date is provided
#         self.anchor = reference_date or datetime.now()
#         self._fday_curr = self.anchor.replace(day=1)

#     @property
#     def context(self):
#         """Returns the calculated date dictionary."""
#         return {
#             "curr_date": self.anchor,
#             "end_prev_month": (self._fday_curr - timedelta(days=1)).strftime(DATE_FMT),
#             "start_curr_month_min1Y": (self._fday_curr - relativedelta(years=1)).strftime(DATE_FMT),
#             "start_curr_month_min2Y": (self._fday_curr - relativedelta(years=2)).strftime(DATE_FMT),
#             "end_3months_before": (self._fday_curr - relativedelta(months=3, days=1)).strftime(DATE_FMT)
#         }

# class DateContext:
#     """
#     Generates dates used across the project.
#     """

#     @staticmethod
#     def get_context():

#         # date_format = "%Y-%m-%d"
        
#         curr_date = datetime.now()
#         fday_curr_month = datetime(curr_date.year, curr_date.month, 1)
#         fday_curr_month_min1y = fday_curr_month - relativedelta(years=1)
#         fday_curr_month_min2y = fday_curr_month - relativedelta(years=2)
#         lday_prev_month = fday_curr_month - timedelta(days=1)
#         lday_three_months_before = lday_prev_month - relativedelta(months=3)
        
#         return {
#             "curr_date": curr_date,
#             "end_prev_month": lday_prev_month.strftime(DATE_FMT),
#             "start_curr_month_min1Y": fday_curr_month_min1y.strftime(DATE_FMT),
#             "start_curr_month_min2Y": fday_curr_month_min2y.strftime(DATE_FMT),
#             "end_3months_before": lday_three_months_before.strftime(DATE_FMT)
#         }

