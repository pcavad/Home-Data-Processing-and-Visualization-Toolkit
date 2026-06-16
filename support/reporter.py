
from datetime import datetime, timedelta
import locale
import re

from numpy._core.defchararray import startswith
from numpy.strings import endswith
locale.setlocale(locale.LC_TIME, "it_IT")
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import ticker, dates
import numpy as np
import pandas as pd
from pathlib import Path
from pydantic import (
    BaseModel,
    validate_call,
    ConfigDict,
    Field,
    DirectoryPath,
    FilePath,
    AfterValidator,
    ValidationInfo,
)
from prophet import Prophet # used in create_expense_report
from termcolor import colored # To color printed text
from typing import Optional, Dict, List, Literal, Annotated, Any

# Helper functions
from .data_manager import load_data

# For input validations
from .validators import (
    validate_date_format,
    check_date_range,
    PositiveInt,
    validate_classification,
)

# Const.
from .config import CLASS_FILTERS_DICT, DATE_FMT

# Dates
from .utils import DateContext
DT_CTX = DateContext() # Dates context


#### CONST. ####

###### Helper models and functions ######


class SavePaths(BaseModel):
    """
    Container for output paths used in data_validation.

    - figure: path where the numeric comparison figure is saved
    - text: path where the textual validation report is saved
    """

    figure: Path
    text: Path


def resampling_fn(df: pd.Series,
    sampling: str = 'M',
    col: str = 'importo',
    function: str = 'sum') -> pd.DataFrame:
    """Resample the dataframe based on a given frequency."""

    return df.set_index('data_operazione').resample(sampling).agg({col: function})


def save_output(content, save_path: Path):
    """
    Save text content or a matplotlib figure to the given path.
    Path is resolved relative to this script's directory.
    
    - If `content` is a string → writes text
    - If `content` is a matplotlib Figure → saves the figure
    """

    try:
        # Parent directory from where THIS script lives
        base_dir = Path(__file__).resolve().parent.parent

        # Full output path
        full_path = (base_dir / save_path).resolve()

        # --- Case 1: Text content -----------------------------------------
        if isinstance(content, str):
            full_path.write_text(content, encoding="utf-8")
            print(f"Text report saved to: {full_path}")
            return

        # --- Case 2: Matplotlib Figure ------------------------------------
        if isinstance(content, matplotlib.figure.Figure):
            content.savefig(full_path, bbox_inches="tight")
            print(f"Figure saved to: {full_path}")
            return

        # --- Case 3: Unsupported -----------------------------------------
        raise TypeError(
            f"Unsupported content type: {type(content)}. "
            "Expected string or matplotlib.figure.Figure."
        )

    except (FileNotFoundError, OSError, TypeError) as e:
        print(f"Error saving output to {save_path}: {e}")


###### Helper functions end ######


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def create_expense_report(df: Optional[pd.DataFrame] = None,
                        date_ctx: Optional[DateContext] = None,
                        start_date: Annotated[Optional[str], AfterValidator(validate_date_format)] = None,
                        end_date: Annotated[Optional[str], AfterValidator(validate_date_format)] = None,
                        filters_dict: Annotated[Optional[Dict[str, List[str]]], AfterValidator(validate_classification)] = None,
                        forecast: Optional[bool] = False,
                        n_periods: PositiveInt = 3) -> pd.DataFrame: # Field(ge=2, le=4) = 3
    """
    Create a tabular report with monthly aggregated expenses, grouped by filters as columns.
    Optionally appends forecasted data using Prophet.

    Args:
        df (pd.DataFrame): The input DataFrame with at least 'classificazione' and 'data_operazione' columns.
        date_ctx (DateContext): date context from utils.py
        start_date (str): Start date for filtering in the format 'YYYY-MM-DD'.
        end_date (str): End date for filtering in the format 'YYYY-MM-DD'.
        filters_dict (dict): Dictionary containing filter names as keys and lists of strings as values 
                             to filter the 'classificazione' column.
        forecast (bool): Whether to append forecasted data to the result DataFrame. Default is False.
        n_periods (int): Number of periods for the forecast if forecast is True. Default is 3.

    Returns:
        pd.DataFrame or None: A DataFrame with monthly aggregated expenses, formatted with 2 decimal places, 
                          or an empty dataframe if an error occurs.
    """

    # Setting defaults
    if df is None:
        df = load_data()

    if date_ctx is None:
        date_ctx = DT_CTX

    if start_date is None:
        start_date = date_ctx.start_curr_month_min1Y

    if end_date is None:
        end_date = date_ctx.end_prev_month

    if filters_dict is None:
        filters_dict = CLASS_FILTERS_DICT

    try:
        # Validazione parametri di ingresso
        check_date_range(start_date, end_date)
    
    except (TypeError, ValueError) as e:
        print(f"Validation error: {e}")
        return pd.DataFrame()

    def forecast_time_series(df: pd.DataFrame, n_periods: int) -> pd.DataFrame:
        """Function to forecast time series data using Prophet and return a DataFrame with 'ds' as index
        and one column per time series.
        """

        # Convert the 'data_operazione' column to datetime if not already
        df['data_operazione'] = pd.to_datetime(df['data_operazione'])
    
        # Prepare a list to store the individual forecast DataFrames
        all_forecasts = []
    
        # Iterate over each time series column (excluding 'data_operazione')
        for column in df.columns[1:]:  # Skip 'data_operazione'
            print(f"Forecasting for: {column}")
            
            # Prepare the data for Prophet
            df_prophet = df[['data_operazione', column]].rename(columns={
                'data_operazione': 'ds',
                column: 'y'
            })
            
            # Initialize and fit the model
            model = Prophet()
            model.fit(df_prophet)
            
            # Create a dataframe for future dates
            future = model.make_future_dataframe(periods=n_periods, freq='M')
            
            # Make predictions
            forecast = model.predict(future)
    
            # Filter out the forecast to only include future dates
            last_date = df['data_operazione'].max()
            forecast_future = forecast[forecast['ds'] > last_date]
            
            # Rename the 'yhat' column to the current time series column for easier pivoting
            forecast_future = forecast_future[['ds', 'yhat']].rename(columns={'yhat': column})
            
            # Add the forecast to the list
            all_forecasts.append(forecast_future.set_index('ds'))
        
        # Concatenate all individual forecasts into a single DataFrame
        forecast_df = pd.concat(all_forecasts, axis=1)
        
        print("Forecasting complete!")
        return forecast_df

    # Filter data based on the date range once for performance improvement
    df['data_operazione'] = pd.to_datetime(df['data_operazione'])
    df = df[(df['data_operazione'] >= start_date) & (df['data_operazione'] <= end_date)]

    # Create the result DataFrame for monthly aggregations
    result_df = pd.DataFrame()

    # Loop over each filter to aggregate data and store it in the result DataFrame
    for filter_name, filter_values in filters_dict.items():
        monthly_agg = resampling_fn(df[df['classificazione'].isin(filter_values)]).rename(columns={"importo":filter_name})
        result_df = pd.concat([result_df, monthly_agg], axis=1)

    # Fill NaN values with 0 and add a 'Total' column
    result_df.fillna(0, inplace=True)
    result_df['Totale'] = result_df.sum(axis=1)

    # Reset index to include the date column and reetting data_operazione again
    result_df = result_df.reset_index().rename(columns={'index': 'data_operazione'})

    # If forecast is True, append forecast data
    if forecast:
        forecast_df = forecast_time_series(result_df, n_periods=n_periods)
        result_df = pd.concat([result_df.set_index('data_operazione'), forecast_df], axis=0)\
            .reset_index().rename(columns={'index': 'data_operazione'})

    # Sort by 'data_operazione' in descending order and round to 2 decimals
    result_df.sort_values('data_operazione', ascending=False, inplace=True)

    # Apply mean to footer (need to change datetime to text and apply proper format)
    result_df["data_operazione"] = result_df["data_operazione"].dt.strftime(DATE_FMT)
    mean_row = result_df.mean(numeric_only=True).to_frame().T
    mean_row["data_operazione"] = "Mean"
    result_df = pd.concat([result_df, mean_row])

    # Round numeric values
    result_df = result_df.round(2)
    
    return result_df


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def create_budget(df: Optional[pd.DataFrame] = None,
                date_ctx: Optional[DateContext] = None,
                year: Optional[int] = Field(default=None, ge=2023, le=DT_CTX.curr_date.year),
                filters_dict: Annotated[Optional[Dict[str, List[str]]], AfterValidator(validate_classification)] = None) -> pd.DataFrame:
    """
    Creates a Pandas pivot table of year-to-date expenses.

    Args:
        df: Pandas DataFrame with expense data.
        date_ctx (DateContext): date context from utils.py
        year: The year for which to create the budget.
        filters_dict: A dictionary of filters for the rows of the pivot table.

    Returns:
        Pandas DataFrame: The pivot table.
    """

    # Setting defaults
    if df is None:
        df = load_data()

    if date_ctx is None:
        date_ctx = DT_CTX

    if year is None:
        year = date_ctx.curr_date.year

    if filters_dict is None:
        filters_dict = CLASS_FILTERS_DICT

    # Filter the DataFrame for the given year
    df['data_operazione'] = pd.to_datetime(df['data_operazione'])  # Ensure it's datetime
    df_filtered = df[df['data_operazione'].dt.year == year].copy() # Create a copy to avoid SettingWithCopyWarning
    # Verify that the filtered DataFrame is not empty
    if df_filtered.empty:
        raise ValueError(f"No data found for the year {year}")
    # Create a 'mese' column
    df_filtered.loc[:, 'mese'] = df_filtered['data_operazione'].dt.strftime('%B')
    # Create a new column 'categoria' that maps descriptions to filter keys
    def get_category(x):
        for key, values in filters_dict.items():
            if x in values:
                return key
        raise ValueError(f"Value '{x}' not found in any filter category")

    df_filtered.loc[:, 'categoria'] = df_filtered['classificazione'].apply(get_category)

    # Create the pivot table
    pivot_df = pd.pivot_table(
        df_filtered,
        values='importo',
        index='categoria',  # Use 'categoria' column for rows
        columns='mese',
        aggfunc='sum',
        fill_value=0,
        margins=True,  # Add totals
        margins_name='Totale',
    )
    # Reorder the columns to start with the months and end with 'Totale'
    month_names_it = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                    'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    # Get the intersection of the actual months in the data and the month_names
    available_months = [month for month in month_names_it if month in pivot_df.columns]
    # Define the desired column order
    desired_columns = available_months + ['Totale']
    # Reindex the pivot table with the new column order
    pivot_df = pivot_df.reindex(columns=desired_columns)

    # Calculate the percentage change vs. previous year
    df_prev_year = df[df['data_operazione'].dt.year == year - 1].copy()
    # Determine the current month
    current_month = pd.to_datetime('today').month
    month_names_it_dict = {i+1: month for i, month in enumerate(month_names_it)}
    current_month_name = month_names_it_dict[current_month]
    # Filter the previous year data up to the month before the current month
    if year == pd.to_datetime('today').year:
        # For the current year set the corrent month to 0 because it is not part of the statistic
        pivot_df.iloc[:, current_month - 1] = 0
        # Calculate totals only up to the current month for consistency
        df_prev_year = df_prev_year[df_prev_year['data_operazione'].dt.month < current_month]
    # Calculate total for each category in the previous year
    if not df_prev_year.empty:
        df_prev_year.loc[:, 'categoria'] = df_prev_year['classificazione'].apply(get_category)
        total_prev_year = df_prev_year.groupby('categoria')['importo'].sum()
    else:
        total_prev_year = pd.Series(index=pivot_df.index, data=0) # Initialize to 0
    # Calculate total for current year
    total_current_year = df_filtered.groupby('categoria')['importo'].sum()
    # Combine the indexes and reindex
    combined_index = total_current_year.index.union(total_prev_year.index)
    total_current_year = total_current_year.reindex(combined_index, fill_value=0)
    total_prev_year = total_prev_year.reindex(combined_index, fill_value=0)
    # Avoid division by zero
    percentage_change = ((total_current_year - total_prev_year) / (total_prev_year.replace(0, 1e-10))) * 100
    # Add the percentage change column. Use .loc to avoid warnings.
    for category, change in percentage_change.items():
        pivot_df.loc[category, '% vs anno prec.'] = f"{change:.2f}%"

    total_percentage_change = ((total_current_year.sum() - total_prev_year.sum()) / 
                                    (total_prev_year.sum() if total_prev_year.sum() != 0 else 1e-10)) * 100
    pivot_df.iloc[-1,-1] = f"{total_percentage_change:.2f}%"

    return pivot_df


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def describe_analysis(transactions_df: Optional[pd.DataFrame] = None,
                    date_ctx: Optional[DateContext] = None,
                    display_html: bool = False) -> pd.DataFrame:
    """
    Generate and display an analysis report, including statistics, monthly totals, and yearly totals.

    Args:
        transactions_df (pd.DataFrame): The input DataFrame containing transaction data.
        date_ctx (DateContext): date context from utils.py
        display_html (bool, optional): If True, the analysis is displayed as an HTML page. Default is True.

    Returns:
        display_result: pd.DataFrame if display_html == False or Markdown object if display_html == True.
    """

    # Setting defaults
    if transactions_df is None:
        transactions_df = load_data()

    if date_ctx is None:
        date_ctx = DT_CTX

    # Calculate date ranges and convert dates to string format
    start_current_year = date_ctx.start_current_year
    start_previous_year = date_ctx.start_previous_year
    start_current_month_minus_one_year = date_ctx.start_current_month_minus_one_year
    start_previous_month = date_ctx.start_previous_month
    end_previous_month = date_ctx.end_previous_month
    end_previous_month_minus_one_year = date_ctx.end_previous_month_minus_one_year
    previous_month_name = date_ctx.previous_month_name
    current_year_name = date_ctx.current_year_name

    # Filter data based on date range and exceptions and columns to exclude from describe()
    cols_to_keep = [col for col in transactions_df.columns if col not in ['essenziale', 'ricorrente']]
    filtered_transactions_df = transactions_df.loc[
        (transactions_df.data_operazione >= start_current_month_minus_one_year) &
        (transactions_df.data_operazione <= end_previous_month),cols_to_keep]

    def calculate_statistics(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate statistics for the given DataFrame."""

        df_describe = pd.concat(
            [resampling_fn(df, 'D').describe(),
            resampling_fn(df, 'W').describe(),
            resampling_fn(df, 'M').describe()]
            , axis=1
        )
        df_describe.columns = ['Giorno', 'Settimana', 'Mese']

        return df_describe
    
    def calculate_monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate totals for the filtered months."""

        df_months = resampling_fn(df, 'M').sort_index(ascending=False)
        df_months.index = [i.strftime('%B') for i in df_months.index]
        df_months.columns = ['Totale']

        return df_months
    
    def calculate_classification_totals(df: pd.DataFrame,
                                        unfiltered_cls: list,
                                        start_previous_month: str, 
                                        previous_month_name: str) -> pd.DataFrame:
        """Calculate totals by classification for the previous month."""

        list_prev_month_cls = [
        [cls_
         , df.loc[(df.classificazione == cls_) 
                                    & (df.data_operazione >= start_previous_month)
                                    , 'importo'].sum()]
        for cls_ in unfiltered_cls]
        
        df_prev_month_cls = pd.DataFrame(list_prev_month_cls, columns=['cls', 'importo'])\
                            .sort_values('importo', ascending=False)\
                            .set_index('cls')
        df_prev_month_cls.index.name = None
        df_prev_month_cls.columns = ['Totale']

        return df_prev_month_cls

    def calculate_classification_delta(df: pd.DataFrame,
                                    unfiltered_cls: list,
                                    start_current_year: str,
                                    end_previous_month: str, 
                                    start_previous_year: str,
                                    end_previous_month_minus_one_year: str) -> pd.DataFrame:
        '''Calculate delta % year on year.'''

        # Using transactions_df instead of filtered_transactions_df
        list_delta_cls = [
        [cls_,
        ((resampling_fn(df.loc[(df.classificazione == cls_)
                    & (df.data_operazione <= end_previous_month)
                    & (df.data_operazione >= start_current_year)])['importo'].sum()
        -
        resampling_fn(df.loc[(df.classificazione == cls_)
                    & (df.data_operazione <= end_previous_month_minus_one_year)
                    & (df.data_operazione >= start_previous_year)])['importo'].sum())
        /
        resampling_fn(df.loc[(df.classificazione == cls_)
                    & (df.data_operazione <= end_previous_month_minus_one_year)
                    & (df.data_operazione >= start_previous_year)])['importo'].sum()
        * 100
        )
        ]
        for cls_ in unfiltered_cls]

        df_delta_cls = pd.DataFrame(list_delta_cls, columns=['cls', 'delta'])\
                            .sort_values('delta', ascending=False)\
                            .set_index('cls')
        df_delta_cls.index.name = None
        df_delta_cls.columns = ['Percentuale']

        return df_delta_cls

    def display_results_html(df_describe: pd.DataFrame,
                            df_last_months: pd.DataFrame,
                            df_prev_month_cls: pd.DataFrame,
                            df_delta_cls: pd.DataFrame,
                            start_current_month_minus_one_year: str,
                            end_previous_month: str,
                            previous_month_name: str,
                            current_year_name: str):
        """Display the analysis results in HTML format and returns a Markdown object."""

        # styler for HTML rendering
        df0_styler = df_describe.style.set_table_attributes("style='display:inline'")\
            .set_caption(f'<b>Da {start_current_month_minus_one_year} a {end_previous_month}</b>')\
            .format('{:,.2f}')
        df1_styler = df_last_months.style.set_table_attributes("style='display:inline'")\
            .set_caption('<b>Ultimi 12 mesi</b>')\
            .format('{:,.2f}')
        df2 = df_prev_month_cls.join(df_delta_cls, how='left')
        df2.columns = [f'{previous_month_name} {current_year_name} (€)',
                        f'% vs anno prec.']
        df2_styler = df2.style.set_table_attributes("style='display:inline'")\
                    .set_caption(f'<b>Classificazioni</b>').format('{:,.2f}')
        
        styler = df0_styler._repr_html_() + df1_styler._repr_html_() + df2_styler._repr_html_()
        
        display(HTML(styler))

        return

    def display_results_text(df_describe: pd.DataFrame,
                            df_last_months: pd.DataFrame,
                            df_prev_month_cls: pd.DataFrame,
                            df_delta_cls: pd.DataFrame,
                            start_current_month_minus_one_year: str,
                            end_previous_month: str,
                            previous_month_name: str,
                            current_year_name: str) -> pd.DataFrame:
        """Format the analysis results for a print out and returns the concatendated df."""
        
        # Concatenate dataframes along axis 1 (columns) and reset the index
        concatenated_df = pd.concat([df_describe.reset_index()
            , df_last_months.reset_index()
            , df_prev_month_cls.join(df_delta_cls, how='left').reset_index()]
            , axis=1, ignore_index=True, )
        concatenated_df.columns = ['', 'Giorno', 'Settimana', 'Mese'
            , '', 'Ultimi 12 mesi'
            , '', f'{previous_month_name} {current_year_name} (€)'
            , f'% vs anno prec.']
        

        return concatenated_df.round(2).fillna('-')

    def display_results(df_describe: pd.DataFrame,
                        df_last_months: pd.DataFrame,
                        df_prev_month_cls: pd.DataFrame,
                        df_delta_cls: pd.DataFrame,
                        display_html: bool,
                        start_current_month_minus_one_year: str,
                        end_previous_month: str,
                        previous_month_name: str,
                        current_year_name: str) -> pd.DataFrame:
        """Display the analysis results and return a dataframe or a markdown object."""

        if display_html:
            # Display results in HTML format
            result_object = display_results_html(df_describe,
                                                df_last_months,
                                                df_prev_month_cls,
                                                df_delta_cls,
                                                start_current_month_minus_one_year,
                                                end_previous_month,
                                                previous_month_name,
                                                current_year_name)
        else:
            # Display results in text format
            result_object = display_results_text(df_describe,
                                                df_last_months,
                                                df_prev_month_cls,
                                                df_delta_cls,
                                                start_current_month_minus_one_year,
                                                end_previous_month,
                                                previous_month_name,
                                                current_year_name)

        return result_object

    # Call the functions and display the results
    display_result = display_results(calculate_statistics(filtered_transactions_df),
                                    calculate_monthly_totals(filtered_transactions_df),
                                    calculate_classification_totals(filtered_transactions_df,
                                                    transactions_df.classificazione.unique(),
                                                    start_previous_month,
                                                    previous_month_name),
                                    calculate_classification_delta(transactions_df,
                                                    transactions_df.classificazione.unique(),
                                                    start_current_year,
                                                    end_previous_month,
                                                    start_previous_year,
                                                    end_previous_month_minus_one_year),
                                    display_html,
                                    start_current_month_minus_one_year,
                                    end_previous_month,
                                    previous_month_name,
                                    current_year_name)

    return display_result


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def generate_report(df: Optional[pd.DataFrame] = None,
                    date_ctx: Optional[DateContext] = None,
                    forecast_expenses: Optional[bool] = False,
                    save_path: Optional[Path] = None):
    """
    Generates and prints a comprehensive budget report including:
    - Descriptive statistics
    - Monthly expenses by category
    - Current year budget
    - Previous year budget

    If a `save_path` is provided, the report is saved to that file.
    The path is resolved relative to the location of this script file.

    Args:
        df (pd.DataFrame, optional): the dataframe, if not provided the functions called will load_data()
        date_ctx (DateContext): date context from utils.py
        forecast_expenses (bool): triggers the Prophet forecast for expenses
        save_path (Path | str, optional): Path (relative to project root) where
            the text report will be saved. If None, the report is only printed
            to the screen. The file is allowed to not exist yet; parent
            directory must exist.
    """

    # Setting default
    if df is None:
        df = load_data()

    if date_ctx is None:
        date_ctx = DT_CTX

    # Width for section separators
    width = 150

    # Generate report sections
    describe_analysis_df = describe_analysis(df, date_ctx = date_ctx)
    create_expense_report_df = create_expense_report(df, date_ctx = date_ctx, forecast=forecast_expenses)
    create_budget_df = create_budget(df, date_ctx = date_ctx)
    create_budget_1_df = create_budget(df, date_ctx = date_ctx, year = date_ctx.curr_date.year - 1)

    # Format the report content
    report_content = ('\n' +
        colored('STATISTICHE DESCRITTIVE: ' + date_ctx.curr_date.strftime('%d-%m-%Y'), 'red', attrs=['bold']) +
        '\n\n' +
        describe_analysis_df.round(2).fillna('-').to_string(index=False) +
        '\n\n' +
        # '#' * width + '\n\n' +
        colored('SPESE PER MESE E CATEGORIA', 'red', attrs=['bold']) +
        '\n\n' +
        create_expense_report_df.round(2).fillna('-').to_string(index=False) +
        '\n\n' +
        # '#' * width + '\n\n' +
        colored('BUDGET ANNO CORRENTE', 'red', attrs=['bold']) +
        '\n\n' +
        create_budget_df.round(2).fillna('-').to_string() +
        '\n\n' +
        # '#' * width + '\n\n' +
        colored('BUDGET ANNO SCORSO', 'red', attrs=['bold']) +
        '\n\n' +
        create_budget_1_df.round(2).fillna('-').to_string() +
        '\n'
    )

    # Save to file if save_path is provided
    if save_path:
        # Strip ANSI color codes before saving to text
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        clean_text = ansi_escape.sub('', report_content)
        save_output(clean_text, Path(save_path))
    else:
        # Print the colored report to screen
        print(report_content)

    return report_content


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def plot_dashboard(df: Optional[pd.DataFrame] = None,
                date_ctx: Optional[DateContext] = None,
                start_date: Annotated[Optional[str], AfterValidator(validate_date_format)] = None,
                end_date: Annotated[Optional[str], AfterValidator(validate_date_format)] = None,
                classification_plot_type: Literal["line", "bar", "cumsum"] = "line",
                classification: Annotated[Optional[str], AfterValidator(validate_classification)] = None,
                fig_params: Dict[str, Any] = {'figsize' : (18,16), 'dpi': 60},
                save_path: Optional[Path] = None):
    '''
    Main plotting function which does:
    - verify the input arguments
    - create the figure which will contain the dashboard
    - Create the plotting subfunction/s
    - Create the plots one for each classification
    - Call the plots
    
    Args:
        df (pd.DataFrame): Input DataFrame containing financial data
        date_ctx (DateContext): date context from utils.py
        start_date (str): Start date in the format 'YYYY-MM-DD'
        end_date (str): End date in the format 'YYYY-MM-DD'
        classification_plot_type (str): draw 'line' or 'bar' plot for each classification
        classification (str): Classification to focus on for certain plots
        fig_params (dict): Figure parameters like size and DPI
        save_path (Path | str, optional): Path (relative to project root) where
            the dashboard figure will be saved. If None, only plots to the
            screen. The file is allowed to not exist yet; parent directory
            must exist. Figure is saved as .png.
    '''

    # Setting defaults
    if df is None:
        df = load_data()

    if date_ctx is None:
        date_ctx = DT_CTX

    if start_date is None:
        start_date = date_ctx.start_curr_month_min2Y

    if end_date is None:
        end_date = date_ctx.end_prev_month

    # Verifying the validity of input arguments
    try:
        check_date_range(start_date, end_date)  
    except (TypeError, ValueError) as e:
        print(f"Validation error: {e}")
        return

    #Creating the different plots

    def fill_missing_months(series: pd.Series, start_date: str, end_date: str) -> pd.Series:
        """Ensures the Series has all months between start_date and end_date, filling missing values with 0."""
        
        # Generate complete date range
        full_index = pd.date_range(start=start_date, end=end_date, freq='M')
        
        # Reindex the series, filling missing months with 0
        return series.reindex(full_index, fill_value=0)

    def plot_trend_and_mean(sr: pd.Series, mean_legend: str = 'Media'):
        '''Plots the trend line and mean value for a Series'''

        # Generate x and y values for plotting
        x = np.arange(len(sr.index))
        y = sr.values.flatten()

        # Plot the linear trendline (red dashed)
        try:
            z = np.polyfit(x, y, 1) # Fit a first-degree polynomial
            p = np.poly1d(z)        # Create polynomial function
            plt.plot(x, p(x), "r--")    # Plot the trendline
        except Exception as e:
            print(f"Error fitting trendline: {e}")

        # Calculate and plot the mean line (green solid)
        sr_mean = np.round(sr.values.mean().item(), 0)
        plt.plot(np.full(len(x), sr_mean), c='g', label=f'{mean_legend}: {sr_mean:.0f}')

    def add_value_labels(ax: plt.Axes, spacing: int = 5, symbol: str = '', min_label: int = 0, rotation: int = 0):
        """
        Add value labels to the end of each bar in a bar chart on the provided axes.

        Args:
            ax (plt.Axes): The axes object where the bar chart is plotted.
            spacing (int, optional): The spacing between the bar and the label. Default is 5.
            symbol (str, optional): The prefix to add before the label. Default is an empty string.
            min_label (int, optional): The minimum value for which the label should be displayed. 
                                       Default is 0.
            rotation (int, optional): The rotation angle for the labels. Default is 0.
        """
        
        # For each bar in the axes
        for rect in ax.patches:
            # Get the height of the bar
            y_value = rect.get_height()
            
            # Calculate the x-coordinate of the center of the bar
            x_value = rect.get_x() + rect.get_width() / 2

            # Define the vertical spacing and alignment for the label based on the bar value
            space = spacing
            va = 'bottom'  # default for positive values
            
            # Adjust space and alignment if the bar value is negative
            if y_value < 0:
                space *= -1
                va = 'top'

            # Format the bar value with the provided symbol (if any)
            label = "{:,.0f}{}".format(y_value, symbol)

            # If the bar value is below the minimum threshold or is zero, don't display the label
            if y_value < min_label or y_value == 0:
                label = ''

            # Create the annotation (label) for the bar
            ax.annotate(
                label,  # Text of the label
                (x_value, y_value),  # Position to place the label (center of the bar)
                xytext=(0, space),  # Offset for the label position
                textcoords="offset points",  # Interpret the offset as points
                ha='center',  # Horizontally center the label
                va=va,  # Vertically align the label based on the bar value
                rotation=rotation)  # Rotate the label as specified

    def make_legend(df_legend: pd.DataFrame) -> list[str]:
        """Helper function to generate a legend based on the mean values of each year."""
    
        # Initialize lists to store mean values and formatted strings
        mean_values = []
        legend_entries = []
    
        # Iterate over the columns (years) in the pivot DataFrame
        for i, year in enumerate(df_legend.columns):
            # Calculate the mean value for the current year ignoring the future periods
            mean_values.append(df_legend[year].replace(0, np.nan).mean())
    
            # Calculate the variance as a percentage for subsequent years
            variance = ''
            if i > 0:
                variance = f'var.: {((mean_values[i] / mean_values[i - 1]) - 1) * 100:+.2f}%'
    
            # Format the legend entry
            legend_entry = f'{year} media: {mean_values[i]:,.0f} {variance}'
            legend_entries.append(legend_entry)
    
        return legend_entries

    def plot_yearly_comparison(ax: plt.Axes,
                               df: pd.DataFrame,
                               start_date: str,
                               end_date: str,
                               classification: str,
                               classification_plot_type: str):
        """Helper function to visualize the yearly comparison of total expenses or a selected classification as a line plot."""
    
        # Calculate the start date of the previous year
        previous_start_date = datetime.strptime(start_date, DATE_FMT) - timedelta(days=365)
        
        # Filter the DataFrame for the previous year and the specified date range
        df_totals = df.loc[(df.data_operazione >= previous_start_date) 
            & (df.data_operazione <= end_date)]
        
        # Resample the total expenses based on the provided classification (if any)
        if classification:
            df_totals = resampling_fn(df_totals.loc[df_totals.classificazione == classification])
            ax.set(title=f'Totale "{classification}" vs anno precedente', xlabel=None)
        else:
            df_totals = resampling_fn(df_totals)
            ax.set(title='Totale vs anno precedente', xlabel=None)
        
        # Extract year and month information for plotting
        df_totals['Anno'] = df_totals.index.year
        df_totals['Mese'] = df_totals.index.strftime('%B')

        # Create a datetime object just for ordering
        df_totals['month_number'] = df_totals.index.month

        # Order the months based on numeric month order
        df_totals = df_totals.sort_values('month_number')
        
        # Pivot table and drop the month_number column before plotting
        # Replace 0 with None to avoid drawing the line for future months
        df_pivot = df_totals.pivot_table(index='Mese', columns='Anno', values='importo', aggfunc='sum').replace(0, None)

        # Ensure the month names are ordered correctly
        df_pivot.index = pd.CategoricalIndex(df_pivot.index, categories=df_totals.sort_values('month_number')['Mese'].unique(), ordered=True)
        df_pivot = df_pivot.sort_index()
        
        # Plot the data as a line plot
        if classification_plot_type == 'cumsum':
            df_pivot.cumsum().plot(kind='line', marker='o', ax=ax)
        else:
            df_pivot.plot(kind='line', marker='o', ax=ax)
        
        # Set plot properties and add legend
        ax.set_xlabel('')
        plt.xticks(rotation=45)
        ax.legend(make_legend(df_pivot))

    def plot_top_vendors(ax: plt.Axes, df: pd.DataFrame, nlargest: int):
        """
        Helper function to plot/print the top vendors based on their aggregated and sorted data."""
    
        # Aggregate and sort data by vendor and select the top nlargest vendors
        df_grouped = df.set_index('data_operazione').groupby('descrizione_standardizzata').agg({'importo': ['sum', 'mean']})\
            .sort_values(('importo', 'sum'), ascending=False).head(nlargest)
    
        # Plotting the bar chart
        ax.bar(np.arange(nlargest), sorted(df_grouped.iloc[:nlargest, 0].values.flatten(), reverse=True))
    
        # Setting the x-axis tick labels and formatting
        _xticklabels = [l[:10].lower() for l in df_grouped.iloc[:nlargest, 0].sort_values(ascending=False).index]
        ax.set(xticks=np.arange(0, nlargest, 1), xticklabels=_xticklabels, yticklabels='', title=f'Top {nlargest} esercizi')
        
        # Adjusting the plot appearance
        ax.spines[['right', 'top']].set_visible(False)
        plt.xticks(rotation=45)
        
        # Adding value labels to the bars
        add_value_labels(ax, rotation=45) 
    
    def plot_channel_product_breakdown(ax: plt.Axes, df: pd.DataFrame):
        """Helper function to visualize the breakdown of expenses by channel as a bar plot."""

        # Calculate the percentage breakdown of expenses by channel
        df_channels = df.groupby('canale').agg({"importo": "sum"}) / df["importo"].sum() * 100

        # Calculate the percentage breakdown by product and service assuming products prevail
        prodotti_value = df['prodotto'].mean() * 100
        servizi_value = 100 - prodotti_value

        # Create the new dataframe
        df_products = pd.DataFrame(
            {'value': [prodotti_value, servizi_value]},
            index=['prodotti', 'servizi'])

        # Define positions
        x_channels = np.arange(len(df_channels.index))  # 0, 1, 2, ...
        x_products = np.arange(len(df_products.index)) + len(df_channels.index) + 1  # space after channels

        width = 0.6

        # Define positions for the two groups
        x_positions = np.array([0, 1])  # 0 for channels group, 1 for products group

        # Define consistent colors
        colors = {
        'negozio': '#1f77b4',   # Blue
        'online': '#ff7f0e',    # Orange
        'prodotti': '#1f77b4',  # Same as negozio
        'servizi': '#ff7f0e'    # Same as online
        }

        # Stack values manually
        # For channels
        canali = ['negozio', 'online']
        channel_values = [df_channels.loc[canale, 'importo'] if canale in df_channels.index else 0 for canale in canali]

        # For products
        prodotti = ['prodotti', 'servizi']
        product_values = [df_products.loc[prod, 'value'] if prod in df_products.index else 0 for prod in prodotti]
        
        # Plot stacked bar for channels
        bottom = 0
        for i, canale in enumerate(canali):
            value = channel_values[i]
            if value > 0:
                ax.bar(x_positions[0], value, width=width, bottom=bottom, color=colors[canale])
                # Add label inside the bar
                ax.text(
                    x_positions[0],
                    bottom + value / 2,
                    f'{canale.capitalize()} ({value:.0f}%)',
                    ha='center',
                    va='center',
                    color='white',
                    fontsize=10,
                    fontweight='bold'
                )
                bottom += value
    
        # Plot stacked bar for products
        bottom = 0
        for i, prod in enumerate(prodotti):
            value = product_values[i]
            if value > 0:
                ax.bar(x_positions[1], value, width=width, bottom=bottom, color=colors[prod])
                # Add label inside the bar
                ax.text(
                    x_positions[1],
                    bottom + value / 2,
                    f'{prod.capitalize()} ({value:.0f}%)',
                    ha='center',
                    va='center',
                    color='white',
                    fontsize=10,
                    fontweight='bold'
                )
                bottom += value

        # Set x-ticks and labels
        ax.set_xticks(x_positions)
        ax.set_xticklabels(['Negozio vs Online', 'Prodotti vs Servizi'], rotation=0)

        # Titles and labels
        ax.set(title='Canale di acquisto / Prodotti vs Servizi', xlabel='', ylabel="Percentuale (%)")

        # Style
        ax.spines[['right', 'top']].set_visible(False)
        ax.set_ylim(0, 100)  # Percentages

    def ess_ric_bar_plot(ax: plt.Axes, df: pd.DataFrame, start_date: str, end_date: str):
        '''
        Creates a bar plot for expense categorization with three comparisons:
        1. Recurring vs Occasional
        2. Essential vs Optional
        3. Essential + Recurring vs Occasional + Optional
        '''
        
        # Compute percentages
        perc_recurring = df["ricorrente"].mean()
        perc_essential = df["essenziale"].mean()
        perc_combined_1 = df[(df["essenziale"] == 1) & (df["ricorrente"] == 1)].shape[0] / df.shape[0]
        perc_combined_0 = df[(df["essenziale"] == 0) & (df["ricorrente"] == 0)].shape[0] / df.shape[0]
        
        # Labels and values
        # categories = ["Ricorrente vs Occasionale", "Essenziale vs Opzionale", "(Ess+Ricc) vs (Occ+Opz)"]
        categories = ["Ricorrente", "Essenziale", "(Ess+Ricc)", "(Occ+Opz)"]
        values = [
            perc_recurring,
            perc_essential,
            perc_combined_1,
            perc_combined_0
        ]
        values = [val * 100 for val in values]
        colors = ["darkblue", "lightblue", "steelblue", "lightskyblue"]
        
        # Create bar plots (c1, c2)
        for i, (label, val, col) in enumerate(zip(categories, values, colors)):
            ax.bar(i, val, color=col, label=label)
        
        # Aesthetics
        ax.set_xticks(range(len(categories)))
        ax.set_xticklabels(categories, rotation=45)
        ax.set_yticklabels('')
        ax.set_title("Tipi di spese")
        ax.spines[['right', 'top']].set_visible(False)

        add_value_labels(ax, symbol='%')
        
    def ess_ric_line_plot(ax: plt.Axes, df: pd.DataFrame, start_date: str, end_date: str):
        '''
        Creates a line plot showing the monthly trend of:
        1. Recurring expenses
        2. Essential expenses
        '''
        
        # Create a new column with Year-Month in a sortable format
        df["year_month"] = pd.to_datetime(df["data_operazione"]).dt.to_period("M")

        # Aggregate data by month
        monthly_stats = df.groupby("year_month").agg(
            perc_essenziale = pd.NamedAgg(column="essenziale", aggfunc=lambda x: x.mean() * 100),
            perc_ricorrente = pd.NamedAgg(column="ricorrente", aggfunc=lambda x: x.mean() * 100)
            ).sort_index()  
        
        # Set the xticks index
        x = np.arange(len(monthly_stats.index))

        # Plot each column as a separate line
        ax.plot(x, monthly_stats["perc_essenziale"], label="Essenziale", marker='o')
        ax.plot(x, monthly_stats["perc_ricorrente"], label="Ricorrente", marker='o')

        # Trend and mean limited to spese essenziali
        plot_trend_and_mean(monthly_stats["perc_essenziale"], 'Media Ess. (%)')
        
        # Aesthetics
        ax.set_xticks(x[::2])
        ax.set_xticklabels(monthly_stats.index[::2].strftime("%B"), rotation=45)
        ax.set(title=f"Andamento spese essenziali e ricorrenti", ylabel="Percentuale (%)")
        ax.spines[['right', 'top']].set_visible(False)
        ax.legend()

    def plot_cls(fig: plt.Figure, df: pd.DataFrame, classification_plot_type: str) -> tuple[int, bool]:
        """
        Generates subplots for each classification category in the given DataFrame, displaying time-series plots of importo values.
        """

        lst_cls = df.classificazione.unique()
        total = float(df['importo'].sum())

        # Sort classifications by total amount spent in descending order
        sorted_cls = sorted(
            lst_cls,
            key=lambda cls: float(df[df.classificazione == cls]['importo'].sum()) / total * 100,
            reverse=True)
    
        # Iterate over each classification to create individual plots
        for i, _cls in enumerate(sorted_cls, start=1):
            # Resample data based on the specified sampling frequency and add padding values for the date range
            df_resampled = fill_missing_months(resampling_fn(df.loc[df.classificazione == _cls, ["data_operazione", "importo"]]),
                                               start_date,
                                               end_date)

            # Create subplot
            ax = fig.add_subplot(len(df.classificazione.unique()) // 4 + 2, 4, i)

            # Handle empty classification with "NO DATA"
            if df_resampled.empty:
                ax.set(title=_cls, xticklabels=[], yticklabels=[])
                ax.annotate('NO DATA', xy=(.5, .5), ha='center', va='center', fontweight='bold')
                continue

            # Calculate total and percentage for current classification
            total_cls = float(df_resampled.sum())
            percentage = total_cls / total * 100

            # Prepare x and y values
            x = np.arange(len(df_resampled.index))
            y = df_resampled.values.flatten()
            xticklabels = df_resampled.index.strftime('%B')

            ax.set_title(f'{_cls} ({total_cls:,.0f}€ - {percentage:.0f}%)')

            # Check if cumulative sum should be plotted
            if classification_plot_type == 'cumsum':
                y = np.cumsum(y)
                yearly_comparison_cumsum = True
            else:
                yearly_comparison_cumsum = False
    
            # Plot based on selected type
            plot_methods = {
                'line': lambda x, y: ax.plot(x, y, marker='o'),
                'bar': lambda x, y: ax.bar(x, y),
                'cumsum': lambda x, y: ax.plot(y, linestyle='-', marker='o')
            }
            plot_methods[classification_plot_type](x, y)
    
            # Add trend and mean to current axis
            plot_trend_and_mean(df_resampled)
    
            # Customize axis
            ax.legend()
            ax.set_xticks(x[::2])
            ax.set_xticklabels(xticklabels[::2], rotation=45)
            ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))

        # Return metadata
        return i, yearly_comparison_cumsum
    
    # Instantiate the main figure for plotting
    fig = plt.figure(num='Dashboard', figsize=fig_params['figsize'], dpi=fig_params['dpi'])
    fig.suptitle(f'Aggregazione per mese, intervallo: {start_date} - {end_date}\n', fontweight='bold')

    # Filter the dataframe based on the date range
    df_dashboard = df.loc[(df.data_operazione >= start_date) & (df.data_operazione <= end_date)]

    # Check if there's data to plot
    if df_dashboard.empty:
        print('No data')
        return

    # Call the function to plot all classifications
    i, yearly_comparison_cumsum = plot_cls(fig, df_dashboard, classification_plot_type)

    # Plot the yearly comparison for total expenses or one specific classifications
    ax0 = fig.add_subplot(i // 4 + 2, 4, i + 1)
    plot_yearly_comparison(ax0, df, start_date, end_date, classification, yearly_comparison_cumsum)
    # Plot the top nlargest vendors
    ax1 = fig.add_subplot(i // 4 + 2, 4, i + 2)
    plot_top_vendors(ax1, df_dashboard, 10)
    # Plot the breakdown of expenses by channel
    ax2 = fig.add_subplot(i // 4 + 2, 4, i + 3)
    plot_channel_product_breakdown(ax2, df_dashboard)
    # Plot bars recurring_vs_occasional
    ax3 = fig.add_subplot(i // 4 + 2, 4, i + 4)
    ess_ric_bar_plot(ax3, df_dashboard, start_date, end_date)
    ax4 = fig.add_subplot(i // 4 + 2, 4, i + 5)
    ess_ric_line_plot(ax4, df_dashboard, start_date, end_date)

    plt.tight_layout()
    prev_backend = matplotlib.get_backend()
    try:
        if save_path:
            matplotlib.use("Agg", force=True)
            save_output(fig, Path(save_path))
            plt.close(fig)
        else:
            plt.show()
    finally:
        matplotlib.use(prev_backend, force=True)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def data_validation(df: Optional[pd.DataFrame] = None,
                    date_ctx: Optional[DateContext] = None,
                    sampling: Literal["D", "M"] = "D",
                    slice_index: int = Field(default=0, ge=0, le=11),
                    end_base: Annotated[Optional[str], AfterValidator(validate_date_format)] = None,
                    end_eval: Annotated[Optional[str], AfterValidator(validate_date_format)] = None,
                    fig_params: Dict[str, Any] = {'figsize' : (14,12), 'dpi': 60},
                    save_paths: Optional[SavePaths] = None):
    '''
    Display statistics and visualizations for data validation.

    Args:
        df (pd.DataFrame): Input DataFrame for data validation.
        date_ctx (DateContext): date context from utils.py
        sampling (str): sampling rate (D=day, M=month)
        slice_index (int): index to slice.
        end_base (str): date end of the base dataset
        end_eval (str): date end of the eval dataset
        fig_params (Dict[str, Any]): figure parameters
        save_paths (SavePaths, optional): Container with:
            - figure (Path): path to save the figure
            - text (Path): path to save the textual report.
            If None, the figure is shown and all text is printed to screen.
    '''

    # Setting default
    if df is None:
        df = load_data()

    if date_ctx is None:
        date_ctx = DT_CTX

    if end_eval is None:
        end_eval = date_ctx.end_prev_month

    if end_base is None:
        end_base = date_ctx.end_3months_before

    # Setting const.
    slice =  {'slice_col': 'classificazione', 'slice_index': slice_index}

    skew = {'cat': ['classificazione', 'descrizione_standardizzata'],
           'num': ['importo'],
           'end_base': end_base,
           'end_eval': end_eval}

    # Collect log messages when saving to file instead of printing
    log_messages: List[str] = []

    def log(msg: str) -> None:
        """
        Log helper: if save_paths is None, print to screen,
        otherwise buffer messages to be written to a text file.
        """
        if save_paths is None:
            print(msg)
        else:
            log_messages.append(msg)

    def visualize_categorical_diff(base_series: pd.Series, eval_series: pd.Series, col_name: str):
        """Display differences in unique values between two categorical series.

        Args:
            - base_series (pd.Series): Series for the base period.
            - eval_series (pd.Series): Series for the evaluation period.
            - col_name (str): column to check for new items.
        """

        diff_base_eval = sorted(
            set(eval_series.unique()).difference(set(base_series.unique()))
        )
        if diff_base_eval:
            log(colored(f'\n{len(diff_base_eval)} new elements in "{col_name}":\n', 'red'))
            log(str(diff_base_eval))
            log("")
        else:
            log(colored(f'\n"{col_name}": no difference', 'red'))

    def visualize_numeric_diff(base_series: pd.Series,
                            eval_series: pd.Series) -> None:
        """Visualize the distribution of a numeric series.

        Args:
            - base_series (pd.Series): Series for the base period.
            - eval_series (pd.Series): Series for the evaluation period.
        """

        def extract_stats(series: pd.Series):
            """Extracts statistic info for a numeric series."""
    
            desc = series.describe().to_dict()
            mode_series = series.mode()
            mode_val = mode_series.max() if not mode_series.empty else None  # First mode only iloc[0]
            return {
                'mode': mode_val,
                'median': series.median(),
                'mean': series.mean(),
                'skewness': series.skew(),
                'count': desc.get('count'),
                'std': desc.get('std'),
                'min': desc.get('min'),
                '25%': desc.get('25%'),
                '50%': desc.get('50%'),
                '75%': desc.get('75%'),
                'max': desc.get('max')}

        base_stats = extract_stats(base_series)
        eval_stats = extract_stats(eval_series)
    
        # Combine into a tidy comparison DataFrame
        rows = []
        for stat in base_stats:
            rows.append({
                'statistic': stat,
                'base': base_stats[stat],
                'eval': eval_stats[stat],
                'diff %': round((eval_stats[stat] - base_stats[stat]) / base_stats[stat], 2) * 100 if base_stats[stat] != 0 else 0})

        result_df = (
            pd.DataFrame(rows)
            .set_index('statistic')
            .apply(pd.to_numeric, errors='ignore')
            .round(2)
        )

        # Log the numeric statistics instead of printing directly
        log(result_df.to_string())

        # Plot the histograms
        fig = plt.figure(num='Data validation', figsize=fig_params['figsize'], dpi=fig_params['dpi'])
        fig.suptitle(f'End base: {end_base}, end eval: {end_eval}\n', fontweight='bold')
        base_series.hist(bins=20, label='base', color='blue', alpha=0.5)
        eval_series.hist(bins=20, label='eval', color='orange', alpha=0.5)
        plt.axvline(base_series.mean(), color='blue', linestyle='dashed',
                    linewidth=2, label=f'Mean (base): {base_series.mean():.2f}')
        plt.axvline(eval_series.mean(), color='orange', linestyle='dashed',
                    linewidth=2, label=f'Mean (eval): {eval_series.mean():.2f}')
        plt.xlim(0, base_series.std() * 3)
        plt.legend()
        plt.title(f"{skew.get('num')[0]} - sampling: {'giorno' if sampling == 'D' else 'mese' if sampling == 'M' else 'niente'}")
        plt.xlabel('x compreso tra 0 e 3 x dev std')

        # Decide whether to show or save the figure
        if save_paths is not None:
            save_output(fig, save_paths.figure)
        else:
            plt.show()

    def slice_info(df_sliced: pd.DataFrame, slice_col: str, slice_index: int) -> pd.DataFrame:
        """Return information about possible slices and the selected slice.

        Args:
            - df_sliced (pd.DataFrame): The DataFrame to slice.
            - slice_col (str): column to slice on
            - slice_index (int): index of the value of slice_col to slice on

        Returns:
            - df_sliced (pd.DataFrame): The DataFrame sliced.

        """

        # Enumerate all the possible unique values in slice_col
        slice_dict = {i: val for i, val in enumerate(df_sliced[slice_col].unique(), start=1)}
        log(colored(f'\nPossible slices:', 'red') + f" {slice_dict}")

        if slice_index == 0:
            log(colored('\n0: all values', 'red', attrs=['bold']))
            return df_sliced
        else:
            try:
                slice_val = slice_dict[slice_index]
                log(colored(f'\nSliced ({slice_index}):', 'red', attrs=['bold']) + f" {slice_val}")
                return df_sliced.loc[df_sliced[slice_col] == slice_val]
            except KeyError:
                log(colored('Invalid slice index, displaying data for index = 0', 'red', attrs=['bold']))
                return df_sliced
        
    try:
        # Check data skewness for categorical and numeric features
        end_base_str = skew['end_base']
        end_eval_str = skew['end_eval']
        # Convert strings to datetime objects
        end_base_dt = datetime.strptime(end_base_str, DATE_FMT)
        end_eval_dt = datetime.strptime(end_eval_str, DATE_FMT)
        
        # Calculate the difference in days
        delta = end_eval_dt - end_base_dt
        days_between = delta.days
        # Apply difference to filter
        start_base_dt = end_base_dt - timedelta(days_between)
        start_base_str = datetime.strftime(start_base_dt, DATE_FMT)

        log(colored(f'\nDATE RANGE BASE: >{start_base_str} and <={end_base_str}', 'red', attrs=['bold']))
        log(colored(f'DATE RANGE EVAL: >{end_base_str} and <={end_eval_str}', 'red', attrs=['bold']))

        # Slicing the dataframe along a categorical column
        log(colored('\nSLICING', 'red', attrs=['bold']))
        df = slice_info(df, slice['slice_col'], slice['slice_index'])

        # Create the base and eval dataframes
        df_base = df.loc[(df.data_operazione <= end_base_dt)
                                 & (df.data_operazione > start_base_dt)]

        df_eval = df.loc[(df.data_operazione <= end_eval_dt)
                                  & (df.data_operazione > end_base_dt)]
        
        # Check categorical features
        log(colored('\nCATEGORICAL FEATURES', 'red', attrs=['bold']))
        for col in skew['cat']:
            visualize_categorical_diff(df_base[col], df_eval[col], col)
        
        # Check numeric features
        log(colored('NUMERIC FEATURES', 'red', attrs=['bold']))

        # Print stats
        for i, col in enumerate(skew['num']):
            # Make temporary copies to avoid modifying original DataFrames
            df_base_tmp = df_base.copy()
            df_eval_tmp = df_eval.copy()
        
            # Apply resampling if any
            if sampling:
                if i == 0:
                    log(f'\nRESAMPLING: {sampling}\n')
                df_base_tmp = resampling_fn(df_base_tmp, sampling, col)
                df_eval_tmp = resampling_fn(df_eval_tmp, sampling, col)
            log(str(col))
            visualize_numeric_diff(df_base_tmp[col], df_eval_tmp[col])
            log("")

        # If we were buffering logs, write them out once
        if save_paths is not None and log_messages:
            # Join messages and strip ANSI color codes before saving
            ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
            clean_text = ansi_escape.sub('', "\n".join(log_messages))
            save_output(clean_text, save_paths.text)

    except Exception as e:
        print(e)
