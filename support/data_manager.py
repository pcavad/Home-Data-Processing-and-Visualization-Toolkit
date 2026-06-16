
import io, json, os, re
# import camelot # extract pdf ### TEMP
from datetime import datetime
import locale
locale.setlocale(locale.LC_TIME, "it_IT")
import pandas as pd
from pathlib import Path

from pydantic import (
    ConfigDict,
    Field,
    FilePath,
    DirectoryPath,
    BaseModel,
    ValidationError,
    model_validator,
    field_validator
)
import shutil # Move files
import sqlite3
from typing import Dict, List, Any, Optional, Annotated, Tuple, Union

# Helper class to manage the TinyDB content
from .metadata_manager import Store

# Config
from .config import (DATA_PATH,
    SQLDB_FILEPATH,
    CSV_FILEPATH,
    JSON_DATA_DICT_FILEPATH,
    CREDIT_CARD_FOLDERS,
    BANK_ACCOUNT_FOLDER,
    COLUMNS,
    TITOLARI,
    PERSONAL_FILES,
    DATE_FMT)

#### Pydantic classes ####

class DataDictModel(BaseModel):
    """Pydantic class to upload the data dict with individual expenses."""
    model_config = ConfigDict(extra="forbid")

    data_operazione: List[str]
    data_registrazione: List[str]
    descrizione: List[str]
    importo: List[float]
    file: List[str]
    titolare: List[str]

    @model_validator(mode='after')
    def check_equal_lengths(self) -> 'DataDictModel':
        lengths = {
            field: len(getattr(self, field))
            for field in self.model_fields
        }
        if len(set(lengths.values())) != 1:
            raise ValueError(f"All lists must have the same length. Got: {lengths}")
        return self

    @field_validator('data_operazione', 'data_registrazione', mode='before')
    @classmethod
    def validate_date_format(cls, v: List[str]) -> List[str]:
        from datetime import datetime
        for date_str in v:
            try:
                datetime.strptime(date_str, DATE_FMT)
            except ValueError:
                raise ValueError(f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD.")
        return v

    @field_validator('file', mode='before')
    @classmethod
    def validate_file(cls, v: List[str]) -> List[str]:
        if not all(f in PERSONAL_FILES for f in v):
            raise ValueError(f"Invalid value in 'file'. Allowed: {PERSONAL_FILES}")
        return v

    @field_validator('titolare', mode='before')
    @classmethod
    def validate_titolare(cls, v: List[str]) -> List[str]:
        if not all(t in TITOLARI for t in v):
            raise ValueError(f"Invalid value in 'titolare'. Allowed: {TITOLARI}")
        return v


class LoadConfig(BaseModel):
    """Pydantic class to load input parameters for load_data"""
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True
    )

    data_path: DirectoryPath = Path(DATA_PATH)
    sqldb_filepath: Annotated[FilePath, Field(validate_default=True)] = Path(SQLDB_FILEPATH)
    csv_filepath: Annotated[FilePath, Field(validate_default=True)] = Path(CSV_FILEPATH)
    data_dict_filepath: Annotated[FilePath, Field(validate_default=True)] = Path(JSON_DATA_DICT_FILEPATH)

    upload_data_dict: bool = False
    include_personal_expenses: bool = True
    credit_card_folders: List[str] = Field(
        default_factory=lambda: CREDIT_CARD_FOLDERS
    )
    bank_account_folders: List[str] = Field(
        default_factory=lambda: BANK_ACCOUNT_FOLDER
    )
    de_duplicate: bool = False
    load_from_sql: bool = True
    with_update: bool = False
    in_place: bool = False
    save_to_sql: bool = False

    @model_validator(mode="after")
    def validate_data_subfolders_exist(self) -> "LoadConfig":
        # Ensure expected subfolders exist under data_path.
        for fold in self.credit_card_folders:
            if not (self.data_path / fold).exists():
                raise ValueError(f"data_path '{fold}' does not exist.")

        for fold in self.bank_account_folders:
            if not (self.data_path / fold).exists():
                raise ValueError(f"data_path '{fold}' does not exist.")

        return self

#### Pydantic classes end ####


def load_data(cfg: Optional[LoadConfig] = None) -> pd.DataFrame:
    '''
    Load data from SQLite file, parse PDF and XLS files, and update the CSV data.

    Args (from LoadConfig):
        data_path (str): The path to the directory containing the data files.
        db_file (str): The SQLite file.
        csv_file (str): The name of the csv file
        json_data_dict (str): The name of the json file to insert one manual transactions
        upload_data_dict (bool): Flag to upload the data dict for manual transactions
        include_personal_expenses (bool): include or exclude personal expenses
        credit_card_folders (list of str): the folders with credit card files (pdf)
        bank_account_folders (list of str): the folders with bank account files (pdf, xlsx)
        de_duplicate (bool): if True it will de-duplicate the duplicated rows.
        load_from_sql (bool): if True load from .db file, if False load from .csv file.
        with_update (bool): Flag to update the data with new PDF files.
        in_place (bool): Flag to update the CSV file in place and move files to staging.
        save_to_sql (bool): Flag to save the data to an SQLite database.

    Returns:
        pd.DataFrame: The DataFrame containing the loaded and updated data.
    '''

    if cfg is None:
        cfg = LoadConfig()

    data_path = cfg.data_path
    sqldb_filepath = cfg.sqldb_filepath
    csv_filepath = cfg.csv_filepath
    data_dict_filepath = cfg.data_dict_filepath
    upload_data_dict = cfg.upload_data_dict
    include_personal_expenses = cfg.include_personal_expenses
    credit_card_folders = cfg.credit_card_folders
    bank_account_folders = cfg.bank_account_folders
    de_duplicate = cfg.de_duplicate
    load_from_sql = cfg.load_from_sql
    with_update = cfg.with_update
    in_place = cfg.in_place
    save_to_sql = cfg.save_to_sql

    # Setting default
    if upload_data_dict:
        json_data_dict_file = data_dict_filepath
    
    # Load data
    try:
        if load_from_sql:
            # Load from SQLite database.
            with sqlite3.connect(sqldb_filepath) as conn:
                # Create a cursor object to execute SQL statements
                c = conn.cursor()
                query = 'SELECT * FROM dataset'
                c.execute(query)
                df = pd.read_sql_query(query, conn)
                c.close()
        else:
            # Load existing data from the CSV file
            df = pd.read_csv(csv_filepath)

        # Convert date columns to datetime format
        df['data_operazione'] = pd.to_datetime(df['data_operazione'], format='%Y-%m-%d')
        df['data_registrazione'] = pd.to_datetime(df['data_registrazione'], format='%Y-%m-%d')

        # include or exclude personal expenses
        if not include_personal_expenses:
            df = df.loc[df.file != 'spesa individuale']

    except Exception as e:
        print(f'Error encountered: {e}')
        return pd.DataFrame(columns=COLUMNS)

    # Update the data if with_update is True
    if with_update:

        def string_to_float(s: str) -> float:
            """ Convert a string to a float, handling specific positive and negative formats."""

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

        def load_transform_card_data(data_path: str, credit_card_folders: list) -> tuple[pd.DataFrame, bool]:
            """Extract credit card transactions from PDF and Excel files in specified folders."""

            try:
                df_list = [] # List to hold individual DataFrames for each file
                file_types = {'.pdf', '.xlsx'}
                
                for folder_name in credit_card_folders:
                    folder_path = os.path.join(data_path, folder_name)
                    files = [f for f in os.listdir(folder_path) if any(f.endswith(ft) for ft in file_types)]
                    for file_name in files:
                        file_path = os.path.join(folder_path, file_name)
                        # Process the PDF files
                        if file_name.endswith('.pdf'):
                            # Extract text from PDF
                            text = extract_text(file_path)
                            # Regex pattern to extract data
                            pattern = re.compile(r'(\d{2}/\d{2}/\d{4})\s(\d{2}/\d{2}/\d{4})\s(.+)')
                            matches = pattern.findall(text)
                            
                            importo, data_1, data_2, descrizione = [], [], [], []
                            # Create a file-like object from the text string
                            f = io.StringIO(text)
                            # Extract data using regex patterns
                            for line in f.readlines():
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
                                'data_operazione': pd.to_datetime(data_1, dayfirst=True, errors='coerce'), # Convert date columns to datetime
                                'data_registrazione': pd.to_datetime(data_2, dayfirst=True, errors='coerce'), # Convert date columns to datetime
                                'descrizione': descrizione,
                                'importo': [string_to_float(i) for i in importo], # Convert 'importo' to float
                                'file': file_name,
                                'titolare': folder_name})
                            
                            if not df_temp.empty:
                                df_list.append(df_temp)
                        # Process the XLSX files
                        elif file_name.endswith('.xlsx'):
                            df_excel = pd.read_excel(file_path)
                            df_excel = df_excel.dropna(how='any') # drop lines with totals and comments
                            df_temp = pd.DataFrame({
                                'data_operazione': pd.to_datetime(df_excel['Data Operazione'], dayfirst=True, errors='coerce'), # Convert date columns to datetime
                                'data_registrazione': pd.to_datetime(df_excel['Data Registrazione'], dayfirst=True, errors='coerce'), # Convert date columns to datetime
                                'descrizione': df_excel['Descrizione Operazione'],
                                'importo': df_excel['Importo (€)'],
                                'file': file_name,
                                'titolare': folder_name})
                            
                            if not df_temp.empty:
                                df_list.append(df_temp)
                    
                if df_list:
                    df_concat = pd.concat(df_list, ignore_index=True)
                    # Handle the introdction of imposta di bollo from March 1st, 2025, for each titolare
                    for df_i in df_list:
                        data_operazione_min = df_i.data_operazione.min()
                        data_operazione_min_str = data_operazione_min.strftime('%Y-%m-%d')
                        if data_operazione_min > datetime(2025,3,1) and df_i.importo.sum() > 77.47:
                            df_bollo, result = dict_to_dataframe({
                                'data_operazione': [data_operazione_min_str],
                                'data_registrazione':[data_operazione_min_str],
                                'descrizione': ['imposta di bollo'],
                                'importo': [2.00],
                                'file': [df_i.file.unique().item()],
                                'titolare': [df_i.titolare.unique().item()]})
                            if result:
                                df_concat = pd.concat([df_concat, df_bollo], ignore_index=True)
                    return df_concat, True
                return pd.DataFrame(columns=COLUMNS), True
            
            except Exception as e:
                print(f'Error "{e}" occurred during card files processing, rolling back.')
                return pd.DataFrame(columns=COLUMNS), False

        def load_transform_bank_data(data_path: str, bank_account_folders: list) -> tuple[pd.DataFrame, bool]:
            """Load and transform bank account data from both XLSX and PDF files."""

            try:
                df_list = []
        
                for folder_name in bank_account_folders:
                    folder_path = os.path.join(data_path, folder_name)
                    files = os.listdir(folder_path)
        
                    # Process Excel files
                    for file_name in [f for f in files if f.endswith('.xlsx')]:
                        # Read Excel file into a DataFrame
                        df_temp = pd.read_excel(os.path.join(folder_path, file_name))
                        # Clean and standardize column names
                        df_temp.columns = [c.replace(' / ', ' ').replace(' ', '_').lower() for c in df_temp.columns]
                        # Drop unnecessary columns
                        df_temp.drop(['canale', 'divisa'], axis=1, inplace=True)
                        # Rename columns
                        df_temp.rename(columns={
                            'data_contabile': 'data_operazione',
                            'data_valuta': 'data_registrazione',
                            'causale_descrizione': 'descrizione'
                            }, inplace=True)
                        # Reorder columns
                        df_temp = df_temp.reindex(['data_operazione', 'data_registrazione', 'descrizione', 'importo'], axis=1)
                        # Append additional columns
                        df_temp['file'] = file_name
                        df_temp['titolare'] = folder_name
                        # Filter out rows related to monthly payments (removed 19.11.25: filtered out in json db file update_exception: True)
                        # df_temp = df_temp[~df_temp.descrizione.str.contains('cartimpronta', na=False)]
                        # Filter out incomes to bank account
                        df_temp = df_temp[df_temp.importo <= 0]
                        # Convert date columns to datetime
                        df_temp['data_operazione'] = pd.to_datetime(df_temp['data_operazione'], format='%d/%m/%Y')
                        df_temp['data_registrazione'] = pd.to_datetime(df_temp['data_registrazione'], format='%d/%m/%Y')
                        # Make 'importo' positive for consistency
                        df_temp['importo'] = df_temp['importo'].abs()
                        if not df_temp.empty:
                            df_list.append(df_temp)
                        print('.', end='')
        
                    # Process PDF files
                    for file_name in [f for f in files if f.endswith('.pdf')]:
                        # extract a dataframe for each page
                        # tables = camelot.read_pdf(os.path.join(folder_path, file_name), flavor='stream', pages='all') ### TEMP
                        processed_dfs = []
                        # process the dataframes as needed
                        for table in tables:
                            # Access table data as a pandas DataFrame and remove the first row
                            df_temp = table.df.iloc[1:]
                            # assign column names as in the new first row
                            df_temp.columns = df_temp.iloc[0]
                            # process the dataframes with logic which depends by the column with amount spent
                            # if the amount spent column exists
                            if 'USCITE' in df_temp.columns.values:
                            # 1) remove the first row 2)
                            # 2) remove all rows in which the amount is ''
                            # 3) keep the relevant columns
                                df_temp = df_temp.iloc[1:].loc[df_temp.USCITE != '']
                                df_temp = df_temp.iloc[:, [0, 1, 3, -1]]
                                # rename the columns
                                df_temp.columns = ['data_registrazione', 'data_operazione', 'importo', 'descrizione']
                                # updating the sort order of the columns to match the history df
                                df_temp = df_temp.reindex(['data_operazione', 'data_registrazione', 'descrizione', 'importo'], axis=1)
                                # create columns for file and titolare
                                df_temp['file'] = file_name
                                df_temp['titolare'] = folder_name
                                # remove rows which concern monthly payments
                                df_temp = df_temp[~df_temp.descrizione.str.contains('CARTIMPRONTA')]
                                # fixing a specific data problem
                                df_temp.loc[df_temp.data_registrazione == '', ['data_registrazione', 'data_operazione', 'importo']] = ['31/03/22', '01/04/22', '- 3,60']
                                # casting dates
                                df_temp['data_registrazione'] = pd.to_datetime(df_temp['data_registrazione'], format='%d/%m/%y')
                                df_temp['data_operazione'] = pd.to_datetime(df_temp['data_operazione'], format='%d/%m/%y')
                                # casting importo as float
                                df_temp.importo = df_temp.importo.apply(string_to_float)
                                # removing rows with incoming money
                                df_temp = df_temp.drop(df_temp.loc[df_temp.importo > 0].index, axis=0)
                                # making all the negative values into positive
                                df_temp.importo = df_temp.importo.abs()
                                if not df_temp.empty:
                                    processed_dfs.append(df_temp)
                        
                        if processed_dfs:
                            df_list.append(pd.concat(processed_dfs, ignore_index=True))
                        print('.', end='')
        
                # Concatenate all individual DataFrames into one
                if df_list:
                    return pd.concat(df_list, ignore_index=True), True
                return pd.DataFrame(columns=COLUMNS), True
            
            except Exception as e:
                print(f'Error "{e}" during bank file processing. Rolling back.')
                return pd.DataFrame(columns=COLUMNS), False

        def upload_data_dict_fn(json_data_dict: str) -> Union[Dict[str, Any], None]:
            """
            Load and validate data_dict from a JSON file using Pydantic.
            """
            try:
                with open(json_data_dict, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                validated = DataDictModel(**config['data_dict'])   # Pydantic validates here
                return validated.model_dump()                       # back to plain dict for downstream use

            except FileNotFoundError as e:
                print(f"File not found: {e}")
            except ValidationError as e:                           # pydantic.ValidationError
                print(f"Validation error:\n{e}")
            except KeyError:
                print("Missing 'data_dict' key in JSON file.")

            return None

        def dict_to_dataframe(data_dict: dict) ->Tuple[pd.DataFrame, bool]:
            """
            Converts a dictionary with specific structure to a Pandas DataFrame.
            
            Args:
            data_dict (dict): The input dictionary with the following structure:
                {
                    'data_operazione': [date string formatted as 'YYYY-MM-DD'],
                    'data_registrazione': [date string formatted as 'YYYY-MM-DD'],
                    'descrizione': [str],
                    'importo': [float],
                    'file': [str],
                    'titolare': [str]
                }
            
            Returns:
            pd.DataFrame: A DataFrame constructed from the input dictionary.
            """
           
            try:    
                # Creazione del DataFrame
                df_temp = pd.DataFrame(data_dict)
            
                # Casting colonne
                df_temp["data_registrazione"] = pd.to_datetime(
                    df_temp["data_registrazione"], format="%Y-%m-%d", errors="raise"
                )
                df_temp["data_operazione"] = pd.to_datetime(
                    df_temp["data_operazione"], format="%Y-%m-%d", errors="raise"
                )
                df_temp["importo"] = df_temp["importo"].astype(float)
            
            except (KeyError, TypeError, ValueError) as e:
                print(f'Validation/formatting error "{e}" during the update of:\n"{data_dict}" → rolling back\n')
                return pd.DataFrame(columns=COLUMNS), False
            except Exception as e:
                # fallback per errori imprevisti
                print(f'Unexpected error "{e}" during the update of:\n"{data_dict}" → rolling back\n')
                return pd.DataFrame(columns=COLUMNS), False
            
            return df_temp, True

        def standardize_description(df: pd.DataFrame, find_descr: list, replace_descr: list) -> pd.DataFrame:
            """Standardize the description column in the DataFrame using the provided dataset setup."""

            def regex_replace(value, find_descr, replace_descr) -> str:
                """Replace descriptions in the value based on regex patterns."""
                
                # Create a list to store the modified values
                modified_values = []
                
                # Iterate over each description and its corresponding replacement
                for find, replace in zip(find_descr, replace_descr):
                    # Generate the regex pattern
                    # re.escape(term_i) ensures the term is treated literally
                    pattern = re.compile('.*' + re.escape(find) + '.*')
                    
                    # Perform the regex search
                    match = pattern.search(value)
                    
                    # If a match is found, replace the description
                    if match:
                        modified_values.append(pattern.sub(replace, value))
                
                # If no matches are found, return the original value
                if not modified_values:
                    return value
                
                # If multiple matches are found
                if len(modified_values) > 1:
                    # If multiple matches are found under the same standardized description
                    # Then we can accept is and go ahead
                    if all(elem == modified_values[0] for elem in modified_values):
                        return modified_values[0]
                    else:
                        # If multiple matches are found under different standardized descriptions
                        # The we need to stop processing
                        print(f"Conflicting regex matches found: {modified_values}")
                        raise ValueError (f"Multiple regex matches found.")
                
                # Otherwise, return the modified value
                return modified_values[0]


            try:
                # Implement the regex to replace the descriptions in find_descr with replace_descr
                df['descrizione_standardizzata'] = df.descrizione.apply(regex_replace, args=(find_descr, replace_descr))

                # Earlier implementation:
                # find_descr_re = ['.*' + desc + '.*' for desc in find_descr]
                # df['descrizione_standardizzata'] = df.descrizione.replace(
                #     find_descr_re, replace_descr, regex=True)
            except Exception as e:
                print(f'Error \"{e}\" during the update of descrizione_standardizzata\nRolling back\n')
                return pd.DataFrame(columns=df.columns)
            return df

        def create_classification(df: pd.DataFrame, classifier_dict: dict) -> pd.DataFrame:
            """Create the classification column based on the standardized description."""

            def find_key(input_dict, value):
                for key in input_dict.keys():
                    if value in input_dict.get(key):
                        return key
                raise UserWarning(f"{value} is missing from dict")
            
            try:
                df['classificazione'] = df.descrizione_standardizzata.apply(lambda x: find_key(classifier_dict, x))
            except UserWarning as u:
                print(f'Error "{u}" during the update of classificazione\nRolling back\n')
                print(f"The classifications are: {list(classifier_dict.keys())}")
                print("-------------------------------------------------------------------")
                return pd.DataFrame(columns=df.columns)
            except Exception as e:
                print(f'Error \"{e}\" during the update of classificazione\nRolling back\n')
                return pd.DataFrame(columns=df.columns)
            return df

        def create_attributes(df: pd.DataFrame, web_list: list, essential_list: list, recurrent_list: list, product_service_list: list, update_exception_list: list) -> pd.DataFrame:
            """Update the DataFrame with channel, essential, and recurrent attributes."""

            try:
                # Use dict for performance
                lookup_essential_dict = dict(essential_list)
                lookup_recurrent_dict = dict(recurrent_list)
                lookup_product_dict = dict(product_service_list)
                df['canale'] = df.descrizione_standardizzata.apply(lambda x: 'online' if x in web_list else 'negozio')
                df['update_exception'] = df.descrizione_standardizzata.apply(lambda x: True if x in update_exception_list else False)
                df['essenziale'] = df.descrizione_standardizzata.apply(lambda x: lookup_essential_dict[x])
                df['ricorrente'] = df.descrizione_standardizzata.apply(lambda x: lookup_recurrent_dict[x])
                df['prodotto'] = df.descrizione_standardizzata.apply(lambda x: lookup_product_dict[x])
            except Exception as e:
                print(f'Error "{e}" during the update of attributes\nRolling back\n')
                return pd.DataFrame(columns=df.columns)
            
            return df

        def check_and_display_duplicates(df: pd.DataFrame, de_duplicate: bool = False) -> pd.DataFrame:
            """Check for duplicated records in a DataFrame and display them if found."""
            
            # 3/3/25 updated to manage the case of duplicated rows across different file names
            # the subset does not include "file" nor "data_registrazione" (this can be different between pdf and xlsx)
            subset_ = ["data_operazione", "descrizione", "importo", "titolare",
                        "descrizione_standardizzata","classificazione"]

            duplicated_count = df.duplicated(subset=subset_).sum()
        
            if duplicated_count > 0:
                print(f'{duplicated_count} duplicated rows found.')
                print('--------------------------------------------------------')
                print(df[df.duplicated(subset=subset_)])
        
                if de_duplicate:
                    # Get the duplicated rows
                    duplicated_rows = df[df.duplicated(subset=subset_, keep=False)]
                    
                    # Create a suffix counter for each group of duplicates
                    duplicate_groups = duplicated_rows.groupby(list(df.columns.difference(['descrizione'])))
                    suffix_counter = duplicate_groups.cumcount() + 1
                    
                    # Append the suffix to the "descrizione" column for each duplicate
                    df.loc[duplicated_rows.index, 'descrizione'] += '_' + suffix_counter.astype(str)
                    
                    print('\n', '----> Duplicated rows have been modified with a suffix in the "descrizione" column. <----', '\n')
                    return df
                else:
                    print('Rolling back!')
                    return pd.DataFrame(columns=df.columns)
            else:
                return df


        # Calling the functions in sequence to stop exection on error
        credit_card_df, success = load_transform_card_data(data_path, credit_card_folders)
        if not success:
            return pd.DataFrame(columns=COLUMNS)
        bank_df, success = load_transform_bank_data(data_path, bank_account_folders)
        if not success:
            return pd.DataFrame(columns=COLUMNS)
        if upload_data_dict:
            dict_df, success = dict_to_dataframe(upload_data_dict_fn(data_dict_filepath))
            if not success:
                return pd.DataFrame(columns=COLUMNS)
        else:
            dict_df = pd.DataFrame(columns=COLUMNS)

        try:
            df = pd.concat([df
                , credit_card_df
                , bank_df
                , dict_df]
                , axis=0)
                    
            df.reindex()

            # Just printing a line break to separate from the next processing.
            print('\n')

        except Exception as e:
            print(f'error \"{e}\" during the update of the files'
                 , 'rolling back\n')
            return pd.DataFrame(columns=COLUMNS)

        # Use the datasetup_proxy_db function for backward compatibility
        try:
            meta_data_manager = Store()
        except ValidationError as e:
            print(e)
            return pd.DataFrame(columns=df.columns)

        classifier_dict, replace_descr, find_descr, web_list, essential_list,\
        recurrent_list, product_service_list, update_exception_list =\
        meta_data_manager.get_metadata_tinydb()

        # Create the descrizione standardizzata
        df = standardize_description(df, find_descr, replace_descr)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Create the classificazione
        df = create_classification(df, classifier_dict)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Create the canale (negozi/online), essenziale and ricorrente (0/1)
        df = create_attributes(df,
                               web_list,
                               essential_list,
                               recurrent_list,
                               product_service_list,
                               update_exception_list)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Check and display duplicated rows or de-duplicate
        df = check_and_display_duplicates(df, de_duplicate)
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        # Filter out exceptions from the exceptions list
        df = df.loc[~df.descrizione_standardizzata.isin(update_exception_list)]


    if df.empty:
        print('\nNote: the dataframe is empty after processing!')
        print('------------------------------------------------')
    else:
        # Sort the DataFrame by the 'data_operazione' column in descending order
        df.sort_values(by='data_operazione', ascending=False, inplace=True)
    
        # Reset the index of the DataFrame
        df.reset_index(drop=True, inplace=True)

    def save_to_db(df: pd.DataFrame, db_path: str):
        '''Save the data from a Pandas dataframe to a SQLite database.'''
    
        try:
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
    
                print('SQL file saved!')
    
        except Exception as e:
            print(f"An error occurred: {e}")
    
    def move_files_to_staging(directory: str, staging: str = 'staging'):
        """Move all '.pdf' and '.xlsx' files within the 1st level of subfolders (except the 'staging' subfolder) to corresponding subfolders under 'staging'."""
        staging_directory = os.path.join(directory, staging)
        
        # Ensure the 'staging' directory exists
        if not os.path.exists(staging_directory):
            os.makedirs(staging_directory)
        
        for root, dirs, files in os.walk(directory):
            # Skip the root directory itself and the 'staging' subdirectory
            if root != directory and staging not in root:
                # Extract the subfolder name relative to the main directory
                relative_subfolder = os.path.relpath(root, directory)
                
                # Create the same subfolder under 'staging' if it doesn't exist
                staging_subfolder = os.path.join(staging_directory, relative_subfolder)
                if not os.path.exists(staging_subfolder):
                    os.makedirs(staging_subfolder)
                
                # Move files ending with '.pdf' or '.xlsx' to the staging subfolder
                for file in files:
                    file_path = os.path.join(root, file)
                    if file.endswith('.pdf') or file.endswith('.xlsx'):
                        new_file_path = os.path.join(staging_subfolder, file)
                        shutil.move(file_path, new_file_path)
                        print(f"Moved: {file_path} to {new_file_path}")

    # Overwrite the CSV file if in_place is True and df hasn't failed before.
    # Move the pdf/xlsx files in the subfolders under the staging directory.
    if in_place and not df.empty:
        try:
            df.to_csv(csv_filepath, index=False)
            move_files_to_staging(data_path)
            print('CSV file saved!')

        except Exception as e:
            print(f"An error occurred when saving to CSV: {e}")
            return pd.DataFrame(columns=df.columns)

    # Save the data to an SQLite database if save_to_sql is True and df hasn't failed before
    if save_to_sql and not df.empty:
        try:
            # Cast the dates as text for compatibility.
            df['data_operazione'] = df['data_operazione'].dt.strftime('%Y-%m-%d')
            df['data_registrazione'] = df['data_registrazione'].dt.strftime('%Y-%m-%d')
            save_to_db(df, sqldb_filepath)
        except Exception as e:
            print(f"An error occurred when saving to db: {e}")
            return pd.DataFrame(columns=df.columns)

    return df