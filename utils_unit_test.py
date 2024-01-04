
import unittest
import os
import re
import pandas as pd
import random
import shutil
import sqlite3
from utils import load_data

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
pd.set_option('display.expand_frame_repr', False)


class TestDataLoading(unittest.TestCase):
    """
    Test case for data loading functionalities.
    """

    def setUp(self):
        """
        Create a temporary directory and populate it with sample files for testing.
        Args:
            pattern_subfolders (str, optional): Regex pattern to create the subfolders. Default pattern matches 'paolo', 'gunda', or 'conto'.
        """

        self.csv_path = 'data/carte.csv'
        self.json_path = 'data/datasetup.json'
        self.root_directory = 'data/staging'
        self.temp_main_folder = "unit_test_data"
        self.pattern_subfolders='(paolo|gunda|conto)'
        self.num_files_to_scramble = 5
        self.verbose = False

        def copy_file(src, dest):
            """Copy a file from source path to destination path."""
            shutil.copy(src, dest)

        if not os.path.exists(self.temp_main_folder):
            os.makedirs(self.temp_main_folder)
            if self.verbose:
                print('------------------------------------')
                print("Main directory created successfully!")

        copy_file(self.csv_path, os.path.join(self.temp_main_folder, 'carte.csv'))
        if self.verbose:
            print("CSV file copied!")

        copy_file(self.json_path, os.path.join(self.temp_main_folder, 'datasetup.json'))
        if self.verbose:
            print("JSON file copied!")

    def tearDown(self):
        """Remove the temporary directory after tests."""

        shutil.rmtree(self.temp_main_folder)
        if self.verbose:
            print("Directory deleted successfully!")
            print('------------------------------------')


    def test_csv_loading(self):
        """Test if CSV files are correctly loaded."""

        data_path = self.temp_main_folder
        # Attempt to load CSV data into a dataframe
        df = load_data(data_path, with_update=False, in_place=False, save_to_sql=False)
        self.assertIsInstance(df, pd.DataFrame), f"Invalid dataframe!"
        print(f'CSV data loaded successfully into a dataframe! {df.shape}')


    def test_data_parsing(self):
        """Test if PDF files are correctly parsed and merged."""

        def copy_file(src, dest):
            """Copy a file from source path to destination path."""
            shutil.copy(src, dest)

        all_files = [os.path.join(root, file) for root, _, files in os.walk(self.root_directory)
                    for file in files if file.endswith('pdf') or file.endswith('xlsx')]
        scrambled_list = random.sample(all_files, len(all_files))
        self.card_bank_files = scrambled_list[:self.num_files_to_scramble]

        for folder in ['paolo', 'gunda', 'conto']:
            os.makedirs(os.path.join(self.temp_main_folder, folder))

        for i, file in enumerate(self.card_bank_files, start=1):
            pattern = re.compile(self.pattern_subfolders, re.IGNORECASE)
            temp_subfolder = re.findall(pattern, file)
            folder_path = os.path.join(self.temp_main_folder, temp_subfolder[0])
            # if not os.path.exists(folder_path):
            #     os.makedirs(folder_path)
            copy_file(file, folder_path)

        if self.verbose:
            print(f"Directory tree created and populated with {i} file/s!")

        data_path = self.temp_main_folder
        # Attempt to read the pdf/xls files and parse them into df
        df = load_data(data_path, with_update=True, in_place=False, save_to_sql=False)
        self.assertIsInstance(df, pd.DataFrame), f"Error while parsing data!"
        print(f'Data parsed successfully! {df.shape}')


    def test_data_integrity(self, expected_schema=None):
        """
        Test if the schema and the data are consistent.
        
        Args:
            expected_schema (dict of str, optional): The columns and their matching types. Defaults to None.
        """

        self.expected_schema = expected_schema or {
                                    'data_acquisto': 'datetime64[ns]',
                                    'data_registrazione': 'datetime64[ns]',
                                    'descrizione': 'object',
                                    'importo': 'float64',
                                    'file': 'object',
                                    'titolare': 'object',
                                    'descrizione_standardizzata': 'object',
                                    'classificazione': 'object',
                                    'canale': 'object'}

        data_path = self.temp_main_folder
        df = load_data(data_path, with_update=False, in_place=False, save_to_sql=False)

        # Checks if the columns match the expected schema
        expected_columns = list(self.expected_schema.keys())
        assert list(df.columns) == expected_columns, f"Unexpected columns found in DataFrame. Expected: {expected_columns}, Got: {list(df.columns)}"

        # Checks if the columns match the expected data types
        for col, dtype in self.expected_schema.items():
            assert df[col].dtype == dtype, f"Unexpected data type for column {col}. Expected: {dtype}, Got: {df[col].dtype}"

        # Checks if there are Null values
        assert df.isnull().sum().sum() == 0, "DataFrame contains null values."

        # Checks if there are duplicated rows
        duplicated_count = df.duplicated().sum()
        assert duplicated_count == 0, f"{duplicated_count} duplicated rows found!"

        print(f'Data integrity verified successfully! {df.shape}')


    def test_data_saving(self):
        """Test if data are saved to CSV and SQL"""

        data_path = self.temp_main_folder
        # Attempt to save the data into a valid CSV file
        df = load_data(data_path, with_update=False, in_place=True, save_to_sql=False)
        csv_file = os.path.join(data_path, 'carte.csv')
        self.assertTrue(os.path.exists(csv_file) and csv_file.endswith('.csv'), f"CSV file '{csv_file}' does not exist.")
        print(f'Data saved to CSV!')

        # Attempt to save the data into a valid SQL .db file
        df = load_data(data_path, with_update=False, in_place=False, save_to_sql=True)
        try:
            db_file = os.path.join(data_path, 'carte.db')
            self.assertTrue(os.path.exists(db_file) and db_file.endswith('.db'), f"SQL file '{db_file}' does not exist.")

            # Attempt to connect to the SQLite database
            conn = sqlite3.connect(db_file)
            conn.close()
            print(f'Data saved to SQL!')
        except sqlite3.Error:
            # If connection fails, assert False
            print(f"{db_file} is not a valid SQLite database.")
            return


if __name__ == '__main__':
    unittest.main()
