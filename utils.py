import datetime, io, json, logging, os, re
from datetime import datetime, timedelta
import camelot # extract pdf
from data import datasetup
import locale
import matplotlib.pyplot as plt
from matplotlib import ticker, dates
import pandas as pd
import numpy as np
from pdfminer.high_level import extract_text # extract pdf
import pprint # pretty printer
from termcolor import colored # To color printed text
import sqlite3
from typing import Optional
import warnings
warnings.filterwarnings("ignore")

from IPython.display import display, HTML

def datasetup_proxy(json_path):
    """
    Proxy function to read and parse a JSON file containing classifications and standardized descriptions.    
    Args:
        json_path (str): The path to the JSON file.    
    Returns:
        dict: A dictionary containing classifications and their matching standardized descriptions.
        list: A list containing standardized descriptions marked as web.
        list: A list containing all standardized descriptions.
        list: A list containing all descriptions.
    """

    # Asserting the existence of the json file
    try:
        assert os.path.exists(json_path) and json_path.endswith('.json')\
            , f"JSON file '{json_path}' does not exist."
    except AssertionError as e:
        print(e)
        return {}, [], [], []

    # Initialize empty lists and dictionary
    classifier_dict = {}
    web_list = []
    standardized_descriptions_list = []
    descriptions_list = []

    # Open and load the JSON file
    with open(json_path, 'r') as file:
        json_data = json.load(file)

    # Iterate through classifications and standardized descriptions in the JSON data
    for classification in json_data["classifications"]:
        classifier_name = classification['name']
        classifier_dict[classifier_name] = []

        for standardized_desc in classification["standardized_descriptions"]:
            standardized_name = standardized_desc['name']
            classifier_dict[classifier_name].append(standardized_name)

            # Add to web_list if standardized description has web attribute set to True
            if standardized_desc['web']:
                web_list.append(standardized_name)

            # Add all descriptions and corresponding standardized descriptions to the lists
            for desc in standardized_desc['descriptions']:
                descriptions_list.append(desc['name'])
                standardized_descriptions_list.append(standardized_name)

    return classifier_dict, web_list, standardized_descriptions_list, descriptions_list


def load_data(data_path: str = 'data'
              , csv_file: str = 'carte.csv'
              , json_file: str = 'datasetup.json'
              , with_update: bool = False
              , in_place: bool = False
              , save_to_sql: bool = False) -> pd.DataFrame:
    '''
    Load data from CSV files, parse PDF files, and update the CSV data.

    This function reads existing data from a CSV file, parses PDF files,
    and updates the data accordingly. It also provides options to update
    the CSV file and save the data to an SQLite database.

    Args:
        data_path (str): The path to the directory containing the data files.
        csv_file (str): The name of the csv file
        json_file (str): The name of the json file
        with_update (bool): Flag to update the data with new PDF files.
        in_place (bool): Flag to update the CSV file in place.
        save_to_sql (bool): Flag to save the data to an SQLite database.

    Returns:
        pd.DataFrame: The DataFrame containing the loaded and updated data.
    '''

    COLUMNS=['data_acquisto', 'data_registrazione', 'descrizione', 'importo'
        , 'file', 'titolare', 'descrizione_standardizzata', 'classificazione', 'canale']

    # Validate the arguments
    try:
        assert os.path.exists(data_path), f"data_path {data_path} does not exist."
        assert os.path.exists(os.path.join(data_path, csv_file)), f"CSV file does not exist."
        assert os.path.exists(os.path.join(data_path, json_file)), f"JSON file does not exist."
        assert isinstance(with_update, bool), 'with_update must be a boolean value'
        assert isinstance(in_place, bool), 'in_place must be a boolean value'
        assert isinstance(save_to_sql, bool), 'save_to_sql must be a boolean value'
    except AssertionError as e:
        print(f"AssertionError: {e}")
        return pd.DataFrame(columns=COLUMNS)

    try:
        # Load existing data from the CSV file
        df = pd.read_csv(os.path.join(data_path, csv_file))

        # Convert date columns to datetime format
        df['data_acquisto'] = pd.to_datetime(df['data_acquisto'], format='%Y-%m-%d')
        df['data_registrazione'] = pd.to_datetime(df['data_registrazione'], format='%Y-%m-%d')

    except FileNotFoundError:
        print('CSV file not found.')
        return pd.DataFrame(columns=COLUMNS)

    except Exception as e:
        print(f'Error encountered: {e}')
        return pd.DataFrame(columns=COLUMNS)

    # Update the data if with_update is True
    if with_update:

        def string_to_float(s: str) -> float:
            """
            Convert a string to a float, handling specific positive and negative formats.
            
            Args:
            - s (str): The input string.
            
            Returns:
            - float: The converted float value.
            """
            # Check if the string ends with '-'
            is_negative = s.endswith('-') or s.startswith('-')
            
            # Remove the '-' character if present
            cleaned_str = s.strip('-')
        
            # Remove commas from the string
            cleaned_str = cleaned_str.replace('.', '').replace(',', '.')
        
            # Convert the cleaned string to float
            result = float(cleaned_str)
        
            # If the number was negative, make it negative again
            if is_negative:
                result = -result
        
            return result

        def extract_credit_card_data(data_path: str):
            """
            Extract credit card transactions from PDF files in specified folders.
        
            Parameters:
            -----------
            data_path : str
                Path to the main data directory.
            Returns:
            --------
            pd.DataFrame
                DataFrame containing extracted credit card transactions.
            bool
                True = success
            """

            try:

                df_list = []  # List to hold individual DataFrames for each file
            
                for d in ['paolo', 'gunda']:
                    folder_path = os.path.join(data_path, d)
                    
                    # Filter out PDF files in the folder
                    file_type = '.pdf'
                    files_pdf = [f for f in os.listdir(folder_path) if f.endswith(file_type)]
                    
                    for file in files_pdf:
                        # Extract text from PDF
                        text = extract_text(os.path.join(folder_path, file))
                        # Regex pattern to extract data
                        pattern = re.compile(r'(\d{2}/\d{2}/\d{4})\s(\d{2}/\d{2}/\d{4})\s(.+)')
                        matches = pattern.findall(text)
                        importo = []   
                        data_1 = []   
                        data_2 = []  
                        descrizione = []
                        
                        # Create a file-like object from the text string
                        f = io.StringIO(text)
                        
                        for line in f.readlines():
                            # Extract data using regex patterns
                            x = re.search(r'\d{2}/\d{2}/\d{4}\s\d{2}/\d{2}/\d{4}\s.+', line)
                            if x:
                                data_1.append(x.group()[:10])               
                                data_2.append(x.group()[11:21])
                                descrizione.append(x.group()[22:])
                            
                            x = re.search(r'\d+,\d{2}-?', line)
                            if x and len(descrizione) > 0 and len(importo) < len(descrizione):
                                importo.append(x.group())
                        
                        # Close the file-like object
                        f.close()
                        
                        # Create a DataFrame from the extracted data
                        df_temp = pd.DataFrame({
                            'data_acquisto': data_1,
                            'data_registrazione': data_2,
                            'descrizione': descrizione,
                            'importo': importo,
                            'file': file,
                            'titolare': d
                        })
            
                        # Convert date columns to datetime
                        df_temp['data_acquisto'] = pd.to_datetime(df_temp['data_acquisto'], format='%d/%m/%Y')
                        df_temp['data_registrazione'] = pd.to_datetime(df_temp['data_registrazione'], format='%d/%m/%Y')
                        
                        # Convert 'importo' to float
                        df_temp['importo'] = df_temp['importo'].apply(string_to_float)
    
                        if not df_temp.empty:
                            df_list.append(df_temp)
                        print('.', end='')
            
                # Concatenate all individual DataFrames into one
                if df_list:
                    return pd.concat(df_list, ignore_index=True), True
                return pd.DataFrame(columns=COLUMNS), True

            except Exception as e:
                print(f'error \"{e}\" during the update of the \"{file_type}\" files'
                     , 'rolling back\n')
                return pd.DataFrame(columns=COLUMNS), False


        def parse_bank_data(data_path: str):
            """
            Parse bank account data from Excel files in the specified folder.
        
            Parameters:
            -----------
            data_path : str
                Path to the data directory.
        
            Returns:
            --------
            pd.DataFrame
                DataFrame containing parsed bank account data.
            bool
                True = success
            """
            
            try:

                df_list = []  # List to hold individual DataFrames for each file
                d = 'conto' # hard coded folder name
            
                folder_path = os.path.join(data_path, d)
                
                # Filter out Excel files in the folder
                file_type = '.xlsx'
                files_excel = [f for f in os.listdir(folder_path) if f.endswith(file_type)]
                
                for file in files_excel:
                    # Read Excel file into a DataFrame
                    df_temp = pd.read_excel(os.path.join(folder_path, file))
                    
                    # Clean and standardize column names
                    df_temp.columns = [c.replace(' / ', ' ').replace(' ', '_').lower() for c in df_temp.columns]
                    
                    # Drop unnecessary columns
                    df_temp.drop(['canale', 'divisa'], axis=1, inplace=True)
                    
                    # Rename columns
                    df_temp.rename(columns={
                        'data_contabile': 'data_acquisto',
                        'data_valuta': 'data_registrazione',
                        'causale_descrizione': 'descrizione'
                    }, inplace=True)
                    
                    # Reorder columns
                    df_temp = df_temp.reindex(['data_acquisto', 'data_registrazione', 'descrizione', 'importo'], axis=1)
                    
                    # Append additional columns
                    df_temp['file'] = file
                    df_temp['titolare'] = d
                    
                    # Filter out rows related to monthly payments and positive transfers
                    df_temp = df_temp[~df_temp.descrizione.str.contains('cartimpronta', na=False)]

                    df_temp = df_temp[df_temp.importo <= 0]
                    
                    # Convert date columns to datetime
                    df_temp['data_acquisto'] = pd.to_datetime(df_temp['data_acquisto'], format='%Y-%m-%d')
                    df_temp['data_registrazione'] = pd.to_datetime(df_temp['data_registrazione'], format='%Y-%m-%d')
                    
                    # Make 'importo' positive for consistency
                    df_temp['importo'] = df_temp['importo'].abs()
    
                    if not df_temp.empty:
                        df_list.append(df_temp)
                    print('.', end='')
            
                # Concatenate all individual DataFrames into one
                if df_list:
                    return pd.concat(df_list, ignore_index=True), True
                return pd.DataFrame(columns=COLUMNS), True

            except Exception as e:
                print(f'error \"{e}\" during the update of the \"{file_type}\" files'
                     , 'rolling back\n')
                return pd.DataFrame(columns=COLUMNS), False

        
        def extract_bank_data(data_path: str):
            """
            Parse all PDF files in the specified directory.
        
            Parameters:
            -----------
            data_path : str
                Path to the data directory.
        
            Returns:
            --------
            pd.DataFrame
                DataFrame containing parsed data from all PDF files.
            bool
                True = success
            """

            try:

                def process_pdf_file(data_path: str, d: str, file: str):
                    """
                    Process a single PDF file to extract relevant data.
                
                    Parameters:
                    -----------
                    data_path : str
                        Path to the data directory.
                
                    Returns:
                    --------
                    pd.DataFrame or None
                        Processed DataFrame containing parsed data, or None if no relevant data is found.
                    """
    
                    # extract a dataframe for each page
                    tables = camelot.read_pdf(os.path.join(data_path, d, file), flavor='stream', pages='all')
                    processed_dfs = []
                
                    # process the dataframes as needed
                    for table in tables:
                        # Access table data as a pandas DataFrame
                        df_temp = table.df
                        # remove the first row
                        df_temp = df_temp.iloc[1:]
                        # assign column names as in the new first row
                        df_temp.columns = df_temp.iloc[0]
                        # process the dataframes with logic which depends by the column with amount spent
                        # if the amount spent column exists
                        if 'USCITE' in df_temp.columns.values:
                            # 1) remove the first row 2)
                            # 2) remove all rows in which the amount is ''
                            # 3) keep the relevant columns
                            df_temp = df_temp.iloc[1:]
                            df_temp = df_temp.loc[df_temp.USCITE != '']
                            df_temp = df_temp.iloc[:,[0,1,3,-1]]
                            # rename the columns
                            df_temp.columns = ['data_registrazione', 'data_acquisto', 'importo', 'descrizione']
                            # updating the sort order of the columns to match the history df
                            df_temp = df_temp.reindex(['data_acquisto', 'data_registrazione', 'descrizione', 'importo'], axis=1)
                            # create columns for file and titolare
                            df_temp['file'] = file
                            df_temp['titolare'] = d
                            # remove rows which concern monthly payments
                            df_temp = df_temp.drop(df_temp.loc[df_temp.descrizione.str.contains('CARTIMPRONTA')].index, axis=0)
                            # fixing a specific data problem
                            df_temp.loc[df_temp.data_registrazione == '', ['data_registrazione', 'data_acquisto', 'importo']] = ['31/03/22', '01/04/22', '- 3,60']
            
                            # casting dates
                            df_temp.data_registrazione = pd.to_datetime(df_temp.data_registrazione, format='%d/%m/%y')
                            df_temp.data_acquisto = pd.to_datetime(df_temp.data_acquisto, format='%d/%m/%y')
                            # casting importo as float
                            df_temp.importo = df_temp.importo.apply(string_to_float)
                            # removing rows with incoming money
                            df_temp = df_temp.drop(df_temp.loc[df_temp.importo > 0].index, axis=0)
                            # making all the negative values into positive
                            df_temp.importo = df_temp.importo.abs()
    
                            if not df_temp.empty:
                                processed_dfs.append(df_temp)
            
                    if processed_dfs:
                        return pd.concat(processed_dfs, ignore_index=True)
                    return pd.DataFrame(columns=COLUMNS)
    
    
                d = 'conto' # hard coded folder name
                # Filter out pdf files in the folder
                file_type = '.pdf'
                files_pdf = [f for f in os.listdir(os.path.join(data_path, d)) if re.search(file_type, f)]
                dfs = []
            
                # Process each file and append the data
                for file in files_pdf:
                    processed_df = process_pdf_file(data_path, d, file)
                    if not processed_df.empty:
                        dfs.append(processed_df)
                    print('.', end='')
    
                if dfs:
                    return pd.concat(dfs, ignore_index=True), True
                return pd.DataFrame(columns=COLUMNS), True

            except Exception as e:
                print(f'error \"{e}\" during the update of the \"{file_type}\" files'
                     , 'rolling back\n')
                return pd.DataFrame(columns=COLUMNS), False

        # Calling the functions in sequence to stop exection on error
        extract_credit_card_df, success = extract_credit_card_data(data_path)
        if not success:
            return pd.DataFrame(columns=COLUMNS)
        parse_bank_df, success = parse_bank_data(data_path)
        if not success:
            return pd.DataFrame(columns=COLUMNS)
        extract_bank_df, success = extract_bank_data(data_path)
        if not success:
            return pd.DataFrame(columns=COLUMNS)

        try:
            df = pd.concat([df
                , extract_credit_card_df
                , parse_bank_df
                , extract_bank_df]
                , axis=0)
                    
            df.reindex()

            # Just printing a line break to separate from the next processing.
            print('\n')

        except Exception as e:
            print(f'error \"{e}\" during the update of the files'
                 , 'rolling back\n')
            return pd.DataFrame(columns=COLUMNS)


        def standardize_description(df: pd.DataFrame, find_descr: list, replace_descr: list):
            """
            Standardize the description column in the DataFrame using the provided dataset setup.
        
            Parameters:
            -----------
            df : pandas.DataFrame
                The DataFrame containing the 'descrizione' column to be standardized.
        
            find_descr (list): descriptions to standardize
            replace_descr (list): standardized descriptions 
        
            Returns:
            --------
            pandas.DataFrame
                The updated DataFrame with the 'descrizione_standardizzata' column.
            """

            try:
                df['descrizione_standardizzata'] = df.descrizione.replace(
                    find_descr, replace_descr, regex=True)
            except Exception as e:
                print(f'Error \"{e}\" during the update of descrizione_standardizzata\nRolling back\n')
                return pd.DataFrame(columns=df.columns)
            return df
        

        def create_classification(df: pd.DataFrame, classifier_dict: dict):
            """
            Create the classification column based on the standardized description.
        
            Parameters:
            -----------
            df : pandas.DataFrame
                The DataFrame containing the 'descrizione_standardizzata' column.
        
            classifier_dict: dict
                A dict containing the classification dictionary.
        
            Returns:
            --------
            pandas.DataFrame
                The updated DataFrame with the 'classificazione' column.
            """

            def find_key(input_dict, value):
                for key in input_dict.keys():
                    if value in input_dict.get(key):
                        return key
                raise UserWarning(f"{value} is missing from dict")
            
            try:
                df['classificazione'] = df.descrizione_standardizzata.apply(lambda x: find_key(classifier_dict, x))
            except UserWarning as u:
                print(f'Error \"{u}\" during the update of classificazione\nRolling back\n')
                print('-------------------------------------------------------------------')
                return pd.DataFrame(columns=df.columns)
            except Exception as e:
                print(f'Error \"{e}\" during the update of classificazione\nRolling back\n')
                return pd.DataFrame(columns=df.columns)
            return df


        def create_channel(df: pd.DataFrame, web_list: list):
            """
            Create the channel column based on the standardized description.
        
            Parameters:
            -----------
            df : pandas.DataFrame
                The DataFrame containing the 'descrizione_standardizzata' column.
        
            web_list: list
                An list containing the web channel list.
        
            Returns:
            --------
            pandas.DataFrame
                The updated DataFrame with the 'canale' column.
            """

            try:
                df['canale'] = df.descrizione_standardizzata.apply(lambda x: 'online' if x in web_list else 'negozio')
            except Exception as e:
                print(f'Error \"{e}\" during the update of canale\nRolling back\n')
                return pd.DataFrame(columns=df.columns)
            return df
 

        def check_and_display_duplicates(df: pd.DataFrame):
            """
            Check for duplicated records in a DataFrame and display them if found.
        
            Parameters:
            -----------
            df : pandas.DataFrame
                The DataFrame to check for duplicates.

            Returns:
            --------
            pandas.DataFrame
                The same DataFrame if the test is passed.
            """

            duplicated_count = df.duplicated().sum()
        
            if duplicated_count > 0:
                print(f'{duplicated_count} duplicated rows found: rolling back!')
                print('--------------------------------------------------------')
                print(df[df.duplicated()])
                return pd.DataFrame(columns=df.columns)
            else:
                return df

        # Use the datasetup_proxy function for backward compatibility
        classifier_dict, web_list, replace_descr, find_descr =\
            datasetup_proxy(os.path.join(data_path, json_file))

        # Create the descrizione standardizzata
        df = standardize_description(df, find_descr, replace_descr)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Create the classificazione
        df = create_classification(df, classifier_dict)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Create the canale (negozi/online)
        df = create_channel(df, web_list)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Check and display duplicated rows
        df = check_and_display_duplicates(df)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

    if df.empty:
        print('\nNote: the dataframe is empty after processing!')
        print('------------------------------------------------')
    else:
        # Sort the DataFrame by the 'data_acquisto' column in descending order
        df.sort_values(by='data_acquisto', ascending=False, inplace=True)
    
        # Reset the index of the DataFrame
        df.reset_index(drop=True, inplace=True)

    # Overwrite the CSV file if in_place is True and df hasn't failed before
    if in_place and not df.empty:
        try:
            df.to_csv(os.path.join(data_path, csv_file), index=False)
        except Exception as e:
            print(f"An error occurred: {e}")

    # Save the data to an SQLite database if save_to_sql is True and df hasn't failed before
    if save_to_sql and not df.empty:
        save_to_db(data_path)

    return df


def save_to_db(data_path: str = 'data', csv_file: str = 'carte.csv', db_file: str = 'carte.db'):
    '''
    Save the data from a CSV file to a SQLite database.

    Args:
        data_path (str): The path to the directory containing the CSV file.
        csv_file (str): The csv file name.
        db_file (str): The SQL file name.
    '''

    csv_path = os.path.join(data_path, csv_file)
    db_path = os.path.join(data_path, db_file)

    try:
        # Read the data from the CSV file into a pandas DataFrame
        df = pd.read_csv(csv_path)

        # Establish a connection to the SQLite database
        with sqlite3.connect(db_path) as conn:
            # Create a cursor object to execute SQL statements
            c = conn.cursor()

            # Drop the existing table if it exists
            c.execute('DROP TABLE IF EXISTS dataset')

            # Create a new table in the SQLite database based on the DataFrame columns
            create_table_sql = f"CREATE TABLE IF NOT EXISTS dataset ({', '.join(df.columns)})"
            c.execute(create_table_sql)

            # Insert data into the SQLite table using parameterized SQL statements
            insert_sql = f"INSERT INTO dataset ({', '.join(df.columns)}) VALUES ({', '.join(['?'] * len(df.columns))})"
            c.executemany(insert_sql, df.values)

            # Commit the changes to the database
            conn.commit()

    except Exception as e:
        print(f"An error occurred: {e}")

    pass  # Placeholder to indicate the end of the function


def resampling_fn(df: pd.DataFrame, _sampling: str = 'M') -> pd.DataFrame:
    """
    Resample the dataframe based on a given frequency.

    Args:
        df (pd.DataFrame): The input dataframe.
        _sampling (str): The resampling frequency (D for days, W for weeks, M for months, Y for years).

    Returns:
        pd.DataFrame: Resampled dataframe.
    """

    return df.set_index('data_acquisto').resample(_sampling).sum()


def is_valid_locale(test_locale: str) -> bool:
    """
    Check if the provided locale is valid.

    Attempt to set the locale; this will raise a ValueError if the locale is not valid.

    Args:
        test_locale (str): The locale string to test.

    Returns:
        bool: True if the locale is valid, False otherwise.
    """

    try:
        locale.setlocale(locale.LC_ALL, test_locale)
        return True
    except locale.Error:
        return False


def is_valid_date_format(date_string: str, date_format: str = '%Y-%m-%d') -> bool:
    """
    Check if the provided date string matches the specified date format.

    Attempt to parse the date using the specified format. If the date string doesn't match the format,
    a ValueError will be raised.

    Args:
        date_string (str): The date string to validate.
        date_format (str): The expected date format string.

    Returns:
        bool: True if the date string matches the format, False otherwise.
    """
    
    try:
        datetime.strptime(date_string, date_format)
        return True
    except ValueError:
        return False


def validate_dict_input(input_dict: dict, required_keys: list):
    '''Check if the provided dictionary has valid type and format

    Args:
        input_dict (dict): input dictionary
        required_keys (list): list of required keys
    '''

    # Assert that input_dict is of type dict
    assert input_dict is None or isinstance(input_dict, dict), "Input must be None or a dictionary"

    # Check if all required keys are present in the input dictionary
    if input_dict is not None:
        missing_keys = [key for key in required_keys if key not in input_dict]
        assert not missing_keys, f"Missing key/s: {', '.join(missing_keys)}"

    pass  # Placeholder to indicate the end of the function


def validate_list_of_strings(input_list):
    '''Check if the provided list has valid type and format

    Args:
        input_list (list): list of strings
    '''

    # Assert that input_list is either None or a list
    assert input_list is None or isinstance(input_list, list), "Input must be None or a list"

    # If input_list is not None, check if all items in the list are strings
    if input_list is not None:
        assert all(isinstance(item, str) for item in input_list), "All items in the list must be strings"


def add_value_labels(ax: plt.Axes, 
                     spacing: int = 5, 
                     symbol: str = '', 
                     min_label: int = 0, 
                     rotation: int = 0):
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

        pass  # Placeholder to indicate the end of the function


def describe_analysis(transactions_df: pd.DataFrame,
                      current_date: datetime = datetime.now(),
                      locale_setting: str = 'it_IT', 
                      display_html: bool = True):
    """
    Generate and display an analysis report, including statistics, monthly totals, and yearly totals.

    Args:
        transactions_df (pd.DataFrame): The input DataFrame containing transaction data.
        current_date (datetime): The current date to calculate statistics backward.
        locale_setting (str, optional): The locale setting for month names. Default is 'it_IT'.
        display_html (bool, optional): If True, the analysis is displayed as an HTML page. Default is True.
    """

    # Assertions to validate the inputs
    try:
        assert isinstance(transactions_df, pd.DataFrame), 'Invalid DataFrame input'
        assert is_valid_locale(locale_setting), f"{locale_setting} is not a valid locale"
        assert isinstance(display_html, bool), 'Display format must be a boolean'
    except AssertionError as e:
        print(f"AssertionError: {e}")
        return

    # Set the locale for month names
    locale.setlocale(locale.LC_TIME, locale_setting)

    # Calculate date ranges
    first_day_current_month = datetime(current_date.year, current_date.month, 1)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    first_day_current_month_minus_one_year = first_day_current_month - timedelta(days=365)
    first_day_previous_month = datetime(last_day_previous_month.year, last_day_previous_month.month, 1)

    # Convert dates to string format
    start_previous_month = first_day_previous_month.strftime('%Y-%m-%d')
    end_previous_month = last_day_previous_month.strftime('%Y-%m-%d')
    start_current_month_minus_one_year = first_day_current_month_minus_one_year.strftime('%Y-%m-%d')
    previous_month_name = first_day_previous_month.strftime("%B")

    # Filter data based on date range and exceptions
    filtered_transactions_df = transactions_df.loc[
        (transactions_df.data_acquisto >= start_current_month_minus_one_year) &
        (transactions_df.data_acquisto <= end_previous_month) &
        (~transactions_df.descrizione_standardizzata.isin(datasetup._exceptions))
    ]


    def calculate_statistics(df: pd.DataFrame = filtered_transactions_df) -> pd.DataFrame:
        """Calculate statistics for the given DataFrame."""
        df_describe = pd.concat(
            [resampling_fn(df, 'D').describe(),
            resampling_fn(df, 'W').describe(),
            resampling_fn(df, 'M').describe()]
            , axis=1
        )
        df_describe.columns = ['Giorno', 'Settimana', 'Mese']

        return df_describe
    
    
    def calculate_last_months_totals(df: pd.DataFrame = filtered_transactions_df
            , last_num_months: int = 8) -> pd.DataFrame:
        """Calculate totals for the last 8 months."""
        df_last_months = resampling_fn(df, 'M').sort_index(ascending=False)[:last_num_months]
        df_last_months.index = [i.strftime('%B') for i in df_last_months.index]
        df_last_months.columns = ['Totale']

        return df_last_months
    
    
    def calculate_classification_totals(df: pd.DataFrame = filtered_transactions_df
            , unfiltered_cls: list = transactions_df.classificazione.unique()
            , start_previous_month: str = start_previous_month
            , last_num_months: int = 8) -> pd.DataFrame:
        """Calculate totals by classification for the previous month."""

        list_prev_month_cls = [
        [_cls
         , df.loc[(df.classificazione == _cls) 
                                    & (df.data_acquisto >= start_previous_month)
                                    , 'importo'].sum()
        ] for _cls in unfiltered_cls]
        
        df_prev_month_cls = pd.DataFrame(list_prev_month_cls, columns=['cls', 'importo'])\
                            .sort_values('importo', ascending=False)\
                            .set_index('cls')[0:last_num_months]
        df_prev_month_cls.index.name = None
        df_prev_month_cls.columns = ['Totale']

        return df_prev_month_cls


    def display_results_html(df_describe: pd.DataFrame
        , df_last_months: pd.DataFrame
        , df_prev_month_cls: pd.DataFrame
        , start_current_month_minus_one_year: str
        , end_previous_month: str 
        , previous_month_name: str):
        """Display the analysis results in HTML format."""
        # styler for HTML rendering
        df0_styler = df_describe.style.set_table_attributes("style='display:inline'")\
            .set_caption(f'<b>Statistiche ultimo anno:<br>da {start_current_month_minus_one_year} a {end_previous_month}</b>')\
            .format('{:,.2f}')
        df1_styler = df_last_months.style.set_table_attributes("style='display:inline'")\
            .set_caption('<b>Ultimi 8 mesi</b>')\
            .format('{:,.2f}')
        df2_styler = df_prev_month_cls.style.set_table_attributes("style='display:inline'")\
            .set_caption(f'<b>Mese di {previous_month_name}</b>')\
            .format('{:,.2f}')
        
        _styler = df0_styler._repr_html_() + df1_styler._repr_html_() + df2_styler._repr_html_()
        
        display(HTML(_styler))
    
    
    def display_results_text(df_describe: pd.DataFrame
            , df_last_months: pd.DataFrame
            , df_prev_month_cls: pd.DataFrame 
            , start_current_month_minus_one_year: str
            , end_previous_month: str 
            , previous_month_name: str):
        """Display the analysis results in text format."""
        # Display statistics for the last year
        print(f'Statistiche ultimo anno: da {start_current_month_minus_one_year} a {end_previous_month}\n')
        pprint.pprint(df_describe.round(2))
        print()
    
        # Display totals for the last 8 months
        print('Ultimi 8 mesi\n')
        pprint.pprint(df_last_months.round(0))
        print()
    
        # Display totals for the previous month
        print(f'Mese di {previous_month_name}\n')
        pprint.pprint(df_prev_month_cls.round(0))
    

    def display_results(df_describe: pd.DataFrame
            , df_last_months: pd.DataFrame
            , df_prev_month_cls: pd.DataFrame
            , display_html: bool
            , start_current_month_minus_one_year: str
            , end_previous_month: str
            , previous_month_name: str):
        """Display the analysis results."""

        if display_html:
            # Display results in HTML format
            display_results_html(df_describe
                , df_last_months
                , df_prev_month_cls
                , start_current_month_minus_one_year
                , end_previous_month
                , previous_month_name)
        else:
            # Display results in text format
            display_results_text(df_describe
                , df_last_months
                , df_prev_month_cls
                , start_current_month_minus_one_year
                , end_previous_month
                , previous_month_name)

    display_results(calculate_statistics()
        , calculate_last_months_totals()
        , calculate_classification_totals()
        , display_html
        , start_current_month_minus_one_year
        , end_previous_month
        , previous_month_name)
    

    pass  # Placeholder to indicate the end of the function


def plot_dashboard(
        df: pd.DataFrame,
        start_date: str,
        end_date: str,
        _sampling: tuple([str]) = (['M', 'mese']),
        _nlargest: int = 10,
        _classification: str = None,
        _locale: str = 'it_IT',
        _fig: dict = {'figsize': (12, 12), 'dpi': 80}
):
    '''
    Plots for different classifications and top 10.
    
    Args:
        df (pd.DataFrame): Input DataFrame containing financial data
        start_date (str): Start date in the format 'YYYY-MM-DD'
        end_date (str): End date in the format 'YYYY-MM-DD'
        _sampling (tuple): Sampling frequency and description
        _nlargest (int): Number of top vendors to plot
        _classification (str): Classification to focus on for certain plots
        _locale (str): Locale for month names
        _fig (dict): Figure parameters like size and DPI
    '''

    # Asserting the validity of input arguments
    try:
        assert isinstance(df, pd.DataFrame), 'df: invalid dataframe'
        assert _sampling in [('M', 'mese'), ('W', 'settimana')], f'{_sampling} can be ("M", "mese"), ("W", "settimana")'
        assert isinstance(_nlargest, int) and 5 <= _nlargest <= 15, f'{_nlargest} must be int 5 - 15'
        assert datetime.strptime(start_date, '%Y-%m-%d'), f"{start_date} invalid date"
        assert datetime.strptime(end_date, '%Y-%m-%d'), f"{end_date} invalid date"
        assert is_valid_locale(_locale), f"{_locale} invalid locale"
        assert _classification is None or _classification in df.classificazione.unique() , f'{_classification} is invalid, valid={lst_cls}'
    except AssertionError as e:
        print(f"AssertionError: {e}")
        return

    # Set up the main figure for plotting
    fig = plt.figure(num='dashboard', figsize=_fig['figsize'], dpi=_fig['dpi'])
    fig.suptitle(f'Aggregazione per "{_sampling[1]}", intervallo: {start_date} - {end_date}\n', fontweight='bold')

    # Filter the dataframe based on the date range and exceptions
    df_dashboard = df.loc[(df.data_acquisto >= start_date) 
        & (df.data_acquisto <= end_date) & (~df.descrizione_standardizzata.isin(datasetup._exceptions))]

    # Check if there's data to plot
    if df_dashboard.empty:
        print('No data')
        return


    def plot_top_vendors(ax: plt.Axes, df: pd.DataFrame, _nlargest: int):
        """
        Helper function to plot the top vendors based on their aggregated and sorted data.
    
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes object on which the bar plot will be drawn.
    
        df : pandas.DataFrame
            The DataFrame containing the data to be plotted. It should have a column named 'data_acquisto'
            and another named 'descrizione_standardizzata'.
    
        _nlargest : int
            The number of top vendors to be displayed on the plot.
        """
    
        # Aggregate and sort data by vendor and select the top _nlargest vendors
        df_grouped = df.set_index('data_acquisto').groupby('descrizione_standardizzata').agg({'importo': ['sum', 'mean']})\
            .sort_values(('importo', 'sum'), ascending=False).head(_nlargest)
    
        # Plotting the bar chart
        ax.bar(np.arange(_nlargest), sorted(df_grouped.iloc[:_nlargest, 0].values.flatten(), reverse=True))
    
        # Setting the x-axis tick labels and formatting
        _xticklabels = [l[:10] for l in df_grouped.iloc[:_nlargest, 0].sort_values(ascending=False).index]
        ax.set(xticks=np.arange(0, _nlargest, 1), xticklabels=_xticklabels, yticklabels='', title=f'Top {_nlargest} vendors')
        
        # Adjusting the plot appearance
        ax.spines[['right', 'top']].set_visible(False)
        plt.xticks(rotation=90)
        
        # Adding value labels to the bars
        add_value_labels(ax, rotation=45)
    
    
    def plot_channel_breakdown(ax: plt.Axes, df: pd.DataFrame, _total: float, _locale: str):
        """
        Helper function to visualize the breakdown of expenses by channel as a bar plot.
    
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes object on which the bar plot will be drawn.
    
        df : pandas.DataFrame
            The DataFrame containing the data to be plotted. It should have a column named 'canale'
            representing the channels and a column with the expenses.
    
        _total : float
            The total value against which the expenses will be normalized to calculate the percentage breakdown.
    
        _locale : str
            A string representing the locale or region for formatting purposes. This can be used to customize
            the appearance of the plot based on regional preferences.
        """

        # Calculate the percentage breakdown of expenses by channel
        (df.groupby('canale').sum() / _total * 100).plot.bar(ax=ax, legend=False)
        
        # Setting plot properties
        ax.set(title='canale', xlabel='', yticklabels='')
        
        # Adjusting the appearance of the plot
        ax.spines[['right', 'top']].set_visible(False)
        
        # Adding value labels to the bars with percentage symbol
        add_value_labels(ax, symbol='%')

    
    def plot_yearly_comparison(ax: plt.Axes, df: pd.DataFrame, start_date: str, end_date: str, _locale: str, _classification: str):
        """
        Helper function to visualize the yearly comparison of total expenses as a line plot.
    
        Parameters:
        -----------
        ax : matplotlib.axes.Axes
            The axes object on which the line plot will be drawn.
    
        df : pandas.DataFrame
            The DataFrame containing the data to be plotted. It should have a column representing the 
            acquisition dates, standardized descriptions, classifications (optional), and expenses.
    
        start_date : str
            A string representing the start date of the comparison period in the format 'YYYY-MM-DD'.
    
        end_date : str
            A string representing the end date of the comparison period in the format 'YYYY-MM-DD'.
    
        _locale : str
            A string representing the locale or region for formatting purposes. This can be used to customize
            the appearance of the plot based on regional preferences.
    
        _classification : str or None
            A string representing the classification for which the expenses will be plotted. If None, 
            the total expenses for all classifications will be plotted.
        """
    
        # Calculate the start date of the previous year
        previous_start_date = datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=365)
        
        # Filter the DataFrame for the previous year and the specified date range
        df_totals = df.loc[(df.data_acquisto >= previous_start_date) 
            & (df.data_acquisto <= end_date) & (~df.descrizione_standardizzata.isin(datasetup._exceptions))]
        
        # Resample the total expenses based on the provided classification (if any)
        if _classification:
            df_totals = resampling_fn(df_totals.loc[df_totals.classificazione == _classification], _sampling[0])
            ax.set(title=f'Totale "{_classification}" vs anno precedente', xlabel=None)
        else:
            df_totals = resampling_fn(df_totals, _sampling[0])
            ax.set(title='Totale vs anno precedente', xlabel=None)
        
        # Extract year and month information for plotting
        df_totals['Anno'] = df_totals.index.year
        df_totals['Mese'] = df_totals.index.month_name(locale=_locale)
        
        # Define the order of months for plotting
        month_order = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno'
            , 'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
        
        # Ensure the month names are ordered correctly
        df_totals['Mese'] = pd.Categorical(df_totals['Mese'], categories=month_order, ordered=True)
        
        # Pivot the DataFrame to have months as rows and years as columns
        df_pivot = df_totals.pivot_table(index='Mese', columns='Anno', values='importo', aggfunc='mean')
        
        # Plot the data as a line plot
        df_pivot.plot(kind='line', ax=ax)
        
        # Set plot properties and add legend
        ax.set_xlabel('')
        ax.legend(make_legend(df_pivot))


    def make_legend(df_legend: pd.DataFrame) -> list:
        """
        Helper function to generate a legend based on the mean values of each year.
    
        Args:
            df_legend (pd.DataFrame): A pivot dataframe with months as the index and years as columns.
    
        Returns:
            list: A list of formatted strings representing the mean values for each year and their variance compared to the previous year.
        """
    
        # Initialize lists to store mean values and formatted strings
        mean_values = []
        legend_entries = []
    
        # Iterate over the columns (years) in the pivot DataFrame
        for i, year in enumerate(df_legend.columns):
            # Calculate the mean value for the current year
            mean_values.append(df_legend[year].mean())
    
            # Calculate the variance as a percentage for subsequent years
            variance = ''
            if i > 0:
                variance = f'var.: {((mean_values[i] / mean_values[i - 1]) - 1) * 100:+.2f}%'
    
            # Format the legend entry
            legend_entry = f'{year} media: {mean_values[i]:,.0f} {variance}'
            legend_entries.append(legend_entry)
    
        return legend_entries


    # Initialize the list of classifications
    lst_cls = df.classificazione.unique()

    # Calculate the total expense over the specified date range
    _total = float(df_dashboard['importo'].sum())

    # Initialize the total for all classifications
    total_all_cls = 0

    # Iterate over each classification to create individual plots
    for i, _cls in enumerate(lst_cls, start=1):
        # Resample data based on the specified sampling frequency
        df_resampled = resampling_fn(df_dashboard.loc[df_dashboard.classificazione == _cls], _sampling[0])

        # If there's no data after resampling, add a placeholder plot
        if df_resampled.empty:
            ax = fig.add_subplot(len(df.classificazione.unique()) // 4 + 2, 4, i)
            ax.set(title=_cls, xticklabels=[], yticklabels=[])
            ax.annotate('NO DATA', xy=(.5, .5), horizontalalignment='center', fontweight='bold')
        else:
            # Calculate the total expense for the current classification
            total_cls = float(df_resampled.sum())
            if total_cls >= total_all_cls:
                most_expensive_cls = _cls
                total_all_cls = total_cls

            # Prepare data for plotting
            x = np.arange(len(df_resampled.index))
            y = df_resampled.values.flatten()
            xticklabels = df_resampled.index.month_name(locale=_locale)

            # Create a subplot for the current classification
            ax = fig.add_subplot(len(df.classificazione.unique()) // 4 + 2, 4, i)
            ax.set_title(_cls + f' ({total_cls/_total * 100:.0f}%)')

            # Plot the actual data
            plt.plot(y)

            # Fit a linear trendline to the data and plot it
            try:
                z = np.polyfit(x, y, 1)
                p = np.poly1d(z)
                plt.plot(x, p(x), "r--")
            except Exception as e:
                print(_cls, e)

            # Add the mean value to the plot
            resampled_mean = np.round(df_resampled.mean().item(), 0)
            plt.plot(np.full(len(xticklabels), resampled_mean), c='g', label=f'Mean: {resampled_mean:.0f}')
            ax.legend()
            ax.set_xticks(x[::2])
            ax.set_xticklabels(xticklabels[::2], rotation=45)
            ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))


        # When all classifications are plotted, add additional plots to the figure
        if i == len(lst_cls):
            # Plot the top _nlargest vendors
            ax0 = fig.add_subplot(i // 4 + 2, 4, i + 1)
            plot_top_vendors(ax0, df_dashboard, _nlargest)

            # Plot the breakdown of expenses by channel
            ax1 = fig.add_subplot(i // 4 + 2, 4, i + 2)
            plot_channel_breakdown(ax1, df_dashboard, _total, _locale)

            # Plot the comparison of total expenses vs the previous year
            ax2 = fig.add_subplot(i // 4 + 2, 4, i + 3)
            plot_yearly_comparison(ax2, df, start_date, end_date, _locale, None)

            # Plot the comparison of total expenses vs the previous year for the most expensive classification
            # or for the classifications specified by _classification
            if _classification is None:
                _classification = most_expensive_cls

            ax3 = fig.add_subplot(i // 4 + 2, 4, i + 4)
            plot_yearly_comparison(ax3, df, start_date, end_date, _locale, _classification)

    plt.tight_layout()
    plt.show()

    pass  # Placeholder to indicate the end of the function


def data_validation(df, _include: list[str] = [], _exclude: list[str] = [], _schema: bool = False
                     , _skew: dict = {}, _slice: dict = {}):
    '''
    Display statistics and visualizations for data validation.

    Args:
        df (pd.DataFrame): Input DataFrame for data validation.
        _include (list of str): Data types to include.
        _exclude (list of str): Data types to exclude.
        _schema (bool): Show DataFrame info().
        _skew (dict): Dictionary for checking data skewness.
        _slice (dict): Dictionary to slice data.
    '''

    # Asserting the validity of input arguments
    try:
        assert isinstance(df, pd.DataFrame), 'df: invalid dataframe'
        validate_list_of_strings(_include)
        validate_list_of_strings(_exclude)
        assert isinstance(_schema, bool), f'{_schema} must be True/False'
        validate_dict_input(_skew, ['cat', 'num', 'filter_base', 'filter_eval'])
        validate_dict_input(_slice, ['slice_col', 'slice_index'])
    except AssertionError as e:
        print(f"AssertionError: {e}")
        return
    except Exception as e:
        print(f"AssertionError: {e}")
        return

    def print_new_items(base_series, eval_series, col_names):
        """
        Print new unique items in specified columns between two DataFrame periods.
        
        Parameters:
        - base_series (pd.DataFrame): DataFrame for the base period.
        - eval_series (pd.DataFrame): DataFrame for the evaluation period.
        - col_names (list): List of columns to check for new items.
        """
        
        # Iterate over specified columns
        for col in col_names:
            # Print column name with red color and bold attributes
            print(colored(f'Nuovi in {col}', 'red', attrs=['bold']))
            print()
            
            # Find new unique items in the evaluation period compared to the base period
            new_items = sorted(set(eval_series[col].unique()).difference(set(base_series[col].unique())))
            
            # Print each new item
            for item in new_items:
                print(item)

    def display_categorical_diff(base_series, eval_series, col_name):
        """Display differences in unique values between two categorical series."""
        diff_base_eval = set(eval_series.unique()) - set(base_series.unique())
        print(colored(f'\n"{col_name}" difference:', 'red'), diff_base_eval)
        print(colored('\nBase schema:', 'blue'), sorted(base_series.unique()))
        print(colored('\nEval schema:', 'green'), sorted(eval_series.unique()))
    
    
    def visualize_numeric_diff(base_series, eval_series, col_name):
        """Visualize the distribution of a numeric series."""
        fig, ax = plt.subplots()
        ax.hist([base_series, eval_series], label=['base', 'eval'])
        ax.legend()
        ax.set_title(col_name)
        plt.show()


    def slice_info(df_sliced, slice_col, slice_index):
        """Return information about possible slices and the selected slice.

        Parameters:
        - df_sliced (pd.DataFrame): The DataFrame to slice.
        - slice_col (str): column to slice on
        - slice_index (int): index of the value of slice_col to slice on

        Returns:
        - df_sliced (pd.DataFrame): The DataFrame sliced.

        """
        # Enumerate all the possible unique values in slice_col
        slice_dict = {i: val for i, val in enumerate(df_sliced[slice_col].unique(), start=1)}
        print(colored(f'Possible slices:', 'red'), slice_dict, '\n')
        
        if slice_index == 0:
            print(colored('\n0: all values', 'red', attrs=['bold']))
            return df_sliced
        else:
            try:
                slice_val = slice_dict[slice_index]
                print(colored(f'\nSliced ({slice_index}):', 'red', attrs=['bold']), slice_val)
                return df_sliced.loc[df_sliced[slice_col] == slice_val]
            except KeyError:
                print(colored('Invalid slice index, displaying data for index = 0', 'red', attrs=['bold']))
                return df_sliced


    def visualize_data(df_plot):
        """
        Visualize data based on the data type of each column in the DataFrame.
        
        Parameters:
        - df_plot (pd.DataFrame): The DataFrame to visualize.
        """
        
        # Iterate over unique data types present in the DataFrame
        for _type in set(df_plot.dtypes):
            # Print the data type with red color and bold attributes
            print(colored(f'\nType: {_type}', 'red', attrs=['bold']))
            
            # Select columns of the current data type
            for _col in df_plot.select_dtypes(include=_type).columns:
                # Create a figure with two subplots: one for statistics table and another for visualization
                fig, (ax1, ax2) = plt.subplots(1, 2, gridspec_kw={'width_ratios': [4, 3]}, dpi=80, figsize=(12, 6))
                
                # Disable axes for the first subplot which will display the statistics table
                ax1.axis('off')
                
                # Prepare data for the statistics table
                table_data = df_plot[_col].describe().reset_index().values
                
                # Display the statistics table on the first subplot
                ax1.table(cellText=table_data,
                          colWidths=[0.2, 0.5],
                          rowLoc='center',
                          cellLoc='left',
                          colLabels=['Stats', 'Values'],
                          loc='left')
                
                # Visualization for object type columns
                if _type == 'object':
                    visualize_object_type(df_plot[_col], ax2)
                # Visualization for numeric type columns
                else:
                    visualize_numeric_type(df_plot[_col], ax2)
                
                # Adjust layout for better proportions and display the figure
                plt.tight_layout()
                plt.show()


    def visualize_object_type(series, ax):
        """
        Visualize the top 10 value counts for a given object type series.
        
        Parameters:
        - series (pd.Series): The series to visualize.
        - ax (matplotlib.axes.Axes): The axis to plot on.
        """
        series.value_counts().head(10).plot(kind='bar', ax=ax)
        plt.title(f'Top 10 for {series.name}')
        plt.xticks(rotation=90)
        xticklabels = [label.get_text()[:10] for label in ax.get_xticklabels()]
        ax.set_xticklabels(xticklabels)


    def visualize_numeric_type(series, ax):
        """
        Visualize the histogram for a given numeric type series.
        
        Parameters:
        - series (pd.Series): The series to visualize.
        - ax (matplotlib.axes.Axes): The axis to plot on.
        """
        series.hist(ax=ax)
        plt.title(series.name)
        plt.grid(False)
        
    
    try:
        # Filter DataFrame based on include and exclude conditions
        if _include or _exclude:
            df_filtered = df.select_dtypes(include=_include, exclude=_exclude)
        else:
            df_filtered = df
        
        # Display DataFrame schema information if requested
        if _schema:
            display(df_filtered.info())
        
        # Check data skewness for categorical and numeric features
        if _skew:
            print(colored('Skewness\n', 'red', attrs=['bold']))
            # Create the base and eval dataframes
            df_base = df_filtered.loc[_skew.get('filter_base', slice(None))]
            df_eval = df_filtered.loc[_skew.get('filter_eval', slice(None))]

            # Check differences in domain values
            print_new_items(df_base, df_eval, ['classificazione', 'descrizione_standardizzata'])
            
            # Check categorical features
            print(colored('\nCategorical features', 'red', attrs=['bold']))
            for _col in _skew.get('cat', []):
                display_categorical_diff(df_base[_col], df_eval[_col], _col)
            
            # Check numeric features
            print(colored('\nNumeric features', 'red', attrs=['bold']))
            for _col in _skew.get('num', []):
                visualize_numeric_diff(df_base[_col], df_eval[_col], _col)
        
        if _slice:
           # Visualize data for each data type for a slice within a specific column
           visualize_data(slice_info(df_filtered, _slice['slice_col'], _slice['slice_index']))
        else:
            # Visualize data for each data type
            visualize_data(df_filtered)

    except Exception as e:
        print(e)

        pass  # Placeholder to indicate the end of the function
