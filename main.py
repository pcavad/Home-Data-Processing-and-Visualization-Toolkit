from datetime import datetime
import sre_compile
import pandas as pd
from pandas.core.frame import ensure_index_from_sequences
pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_colwidth', 30)
pd.set_option('display.max_rows', None)
from pathlib import Path
from pprint import pprint
from pydantic import ValidationError
import re, sys

from support import DataManager, Reporter, MetaDataManager, DateContext, SavePaths

ctx = DateContext() # Dates context
# print(ctx.model_dump_json(indent=2))

try:

	##### Metadata in no SQL db #####

	"""

	"""
	
	# Helper class to manage the TinyDB content
	if False:
		with MetaDataManager() as store:
	
			store.insert_document( 
				doc = {'classification': 'shopping',
			  	'descriptions': [],
			  	'essential': 0,
			  	'name': "PAYPAL *MOONEY 02872941",
			  	'product_service': 0,
			  	'recurrent': 0,
			  	'update_exception': False,
			  	'web': True})

except ValidationError as e:
	print(e)


try:
	if True:
	
	# Try block for pydantic validations
		
		##### Loading #####
	
		# Load the data and update the database
		cfg = DataManager.cfg(
			with_update=False,
			upload_data_dict=False,
			load_from_sql=True,
			in_place=False,
			save_to_sql=False,
			de_duplicate=False,
			include_personal_expenses=True,
		)
	
		df = DataManager.load(cfg)
		print(df.shape)

		#### Reporting #####

		Reporter.report(df,
						date_ctx = ctx,
						forecast_expenses=True,
						save_path = Path("./report/reports.txt"))
		
		#### Dashboard ####
		
		Reporter.dashboard(df = df,
		    		   start_date = ctx.start_curr_month_min2Y, # start_curr_month_min1Y
		    		   end_date = ctx.end_prev_month,
					   classification_plot_type = 'line', # bar, line, cumsum
					   classification = None,
					   save_path = Path("report/dashboard.png"))
		
		##### Data Validation #####
		
		Reporter.validate(df = df,
				sampling = 'D', # D, M
		        slice_index = 0,
		        end_base = ctx.end_3months_before,
		        end_eval = ctx.end_prev_month,
				save_paths = SavePaths(figure=Path("report/numeric_diff.png"), text=Path("report/validation.txt")))
	
except ValidationError as e:
	print(f"ValidationError: {e}")
except Exception as e: 
	print(f"Generic Exception: {e}")

