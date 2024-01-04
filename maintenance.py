
import pandas as pd
pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_colwidth', None)

from utils import *
from utils_json import update_json

df = load_data(with_update = False
              , in_place = False
              , save_to_sql = False)

print(df.shape)

# missing = ".*.*"
# update_json("data/datasetup.json", ["viaggi", "Fondazione Castiglioni", [missing], True], True)

# plot_dashboard(df, '2023-01-01', '2023-12-31'
# 	, _sampling = ('M', 'mese')
# 	, _nlargest = 10
# 	, _classification = None
# 	, _fig = {'figsize' : (14,14), 'dpi': 80})

# describe_analysis(df, datetime.now(), 'it_IT', False)

# kwargs_skew = {'cat': ['classificazione']
#            , 'num': ['importo']
#            , 'filter_base': (df.data_acquisto >= '2023-01-01') & (df.data_acquisto <= '2023-06-30')
#            , 'filter_eval': df.data_acquisto >= '2023-07-01'}

# kwargs_slice = {'slice_col': 'classificazione', 'slice_index': 0}

# data_validation(
#     df = df # NO resampling
#     , _include = ['object', 'number']
#     , _exclude = None # 'object'
#     , _skew = None # kwargs_skew
#     , _slice = None # kwargs_slice
#     , _schema = False)



