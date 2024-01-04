import unittest
import json
from utils_json import construct_json

"""
To create a unit test for the construct_json function, you can use Python's built-in unittest framework.
Below is a unit test that asserts the size of the returned json_data with respect to each input argument.

Here's a breakdown of the unit test:

- The setUp method sets up the sample data and calculates the expected lengths.
- The test_construct_json method calls the construct_json function with the sample data.
- It then reads the saved JSON data from the temporary output file.
- Finally, it asserts that the length of the "classifications" key in the saved JSON data matches the expected length
"""

class TestConstructJson(unittest.TestCase):

    def setUp(self):
        # Sample data
        self.find_descr = ["'.*AMAZON.*'", "*ARIMONDO.*"]
        self.replace_descr = ["AMAZON", "PAM"]
        self.web_list = ["True", "False"]
        self.classifier_dict = {"spesa": ["AMAZON", "PAM"]}

        # Expected lengths
        self.expected_classifications_length = len(self.classifier_dict)

    def test_construct_json(self):
        # Define the output file path (temporary for testing purposes)
        output_file_path = "test_output.json"

        # Call the function
        json_data = construct_json(
            self.find_descr,
            self.replace_descr,
            self.web_list,
            self.classifier_dict,
            output_file_path
        )

        # Load the saved JSON data from the output file
        with open(output_file_path, 'r') as f:
            saved_json_data = json.load(f)

        # Assertions
        self.assertEqual(len(saved_json_data["classifications"]), self.expected_classifications_length)
        
        # Clean up: Remove the temporary output file
        import os
        os.remove(output_file_path)

if __name__ == "__main__":
    unittest.main()


from utils_json import update_json

class TestUpdateJson(unittest.TestCase):

    def setUp(self):
        # Create a sample JSON file for testing
        self.file_path = "test_data.json"
        with open(self.file_path, 'w') as file:
            json.dump({
                "classifications": [
                    {
                        "name": "spesa",
                        "standardized_descriptions": [
                            {
                                "name": "BOTTIGLIERIA BERTA",
                                "web": False,
                                "descriptions": [{"name": "Desc_1"}]
                            }
                        ]
                    }
                ]
            }, file, indent=4)

    def test_add_data_successfully(self):
        data_list = ["spesa", "NUOVA BOTTIGLIERIA BERTA", ("Desc_2", "Desc_3"), False]
        update_json(self.file_path, data_list, _add=True)

        with open(self.file_path, 'r') as file:
            data = json.load(file)
            self.assertTrue(any(desc["name"] == "NUOVA BOTTIGLIERIA BERTA" for desc in data["classifications"][0]["standardized_descriptions"]))
            self.assertTrue(any(desc["name"] == "Desc_2" for desc in data["classifications"][0]["standardized_descriptions"][0]["descriptions"]))

    def test_remove_data_successfully(self):
        data_list = ["spesa", "NUOVA BOTTIGLIERIA BERTA", ("Desc_1",), False]
        update_json(self.file_path, data_list, _add=False)

        with open(self.file_path, 'r') as file:
            data = json.load(file)
            self.assertFalse(any(desc["name"] == "NUOVA BOTTIGLIERIA BERTA" for desc in data["classifications"][0]["standardized_descriptions"]))

    def test_classification_not_exist(self):
        data_list = ["invalid_classification", "BOTTIGLIERIA BERTA", ("Desc_1",), True]
        with self.assertRaises(ValueError):
            update_json(self.file_path, data_list, _add=True)

    def test_standardized_description_already_exists(self):
        data_list = ["spesa", "BOTTIGLIERIA BERTA", ("Desc_1",), True]
        with self.assertRaises(ValueError):
            update_json(self.file_path, data_list, _add=True)

    def tearDown(self):
        # Remove the sample JSON file after testing
        import os
        # os.remove(self.file_path)

if __name__ == "__main__":
    unittest.main()




