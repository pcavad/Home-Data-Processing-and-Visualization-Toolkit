import json, re, os
import pandas as pd
from utils import datasetup_proxy


def update_json(file_path, data_list, add_remove):
    """
    Update a JSON object by adding or removing data based on the provided list.

    Args:
    - file_path (str): Path to the JSON file.
    - data_list (list): List of data to add or remove. Note the relationship between "Standardized_Desc_name" and the list ["Desc_1", "Desc_2", ...]:
                        The "Standardized_Desc_name" is used with 2 objectives:
                        Obj 1: simplify a description "Desc_n" which may be too long or complicated to plot.
                        Obj 2: map multiple descriptions "Desc_1", ..., "Desc_n" to a more general description.
                        For Obj 2 care is necessary to avoid that a description "Desc_n" complies with multiple regex patterns as .*Desc_n.*
                        Example 1: ["Classification_Name", "Standardized_Desc_name", ["Desc_1", "Desc_2", ...], web (bool)]
                                    "Desc_1", "Desc_2", ... may be have a different case or be totally different in different transactions.
                        Example 2: ["Classification_Name", "Standardized_Desc_name", [], web (bool)]
                                    The description is fine to be used as standardized description because it's already short and simple.
                        Example 3: ["Classification_Name", "Standardized_Desc_name", ["Desc_1"], web (bool)]
                                    Desc_1 would be replaced by a more simple standardized description.
                              
    - add_remove (bool): True to add the data, False to remove the data.
    
    Raises:
    - ValueError: If the data_list already exists when trying to add or doesn't exist when trying to remove.
    """

    def validate_input_list(input_list):
        """
        Main function to validate input parameters.
        
        Args:
        - input_list (list): A list containing ["classification name", "standardized description", [zero or many descriptions], boolean value]
        
        Returns:
        - bool: True if input parameters are valid, False otherwise
        """
        
        if len(input_list) < 4:
            print("The input list must have 4 elements: 'classification name', 'standardized description', a list with descriptions or empty, a boolean value.")
            return False
        
        classification_name = input_list[0]
        standardized_description = input_list[1]
        descriptions = input_list[2]
        web = input_list[3]
        
        # Validate classification name
        if classification_name is None or classification_name.strip() == "":
            print("Error: 'classification name' cannot be an empty string or None.")
            return False
        
        # Validate standardized description
        if standardized_description is None or standardized_description.strip() == "":
            print("Error: 'standardized description' cannot be an empty string or None.")
            return False
        
        # Validate each description in the list
        if descriptions is None:
            print("Error: 'descriptions' cannot be None.")
            return False   
        for desc in descriptions:
            if desc is None or desc.strip() == "":
                print("Error: Each description in the list cannot be an empty string or None.")
                return False
    
        # Validate web
        if web is None:
            print("Error: 'web' cannot be None.")
            return False
        
        return True

    try:
        assert os.path.exists(file_path), f"JSON file does not exist."
        result = validate_input_list(data_list)
        assert result, f"Errors in {data_list}"
        assert isinstance(add_remove, bool), f'Add/remove input must be bool'
    except AssertionError as e:
        print(f"AssertionError: {e}")
        return

    def save_to_json(file_path):
        '''Helper function to save the updated JSON data back to the file'''
        with open(file_path, 'w') as file:
            json.dump(json_data, file, indent=4)
        print(f"Updated JSON data saved to '{file_path}'.")

    try:
        # Load the existing JSON data from the file
        with open(file_path, 'r') as file:
            json_data = json.load(file)
    
        classification_name = data_list[0]
        standardized_desc_name = data_list[1]
        descriptions = list(data_list[2])
        web = data_list[-1]

        # Check if data_list doesn't exist if add_remove is False
        if all(classification_name not in classification['name'] for classification in json_data['classifications']):
            raise ValueError(f"No existing classification '{classification_name}' found to add data.")

        # Search for the classification in the JSON data
        for classification in json_data["classifications"]:
            if classification["name"] == classification_name:
                # Check if the standardized description name exists under the classification
                for standardized_desc in classification["standardized_descriptions"]:
                    # If it exists...
                    if standardized_desc["name"] == standardized_desc_name:
                        # If you want to remove it than go ahead and terminate the outer loop
                        if not add_remove:
                            # Remove the data from the JSON object
                            classification["standardized_descriptions"].remove(standardized_desc)
                            print(f"Data for '{standardized_desc_name}' under '{classification_name}' removed successfully.")
                            save_to_json(file_path)
                            return
                        else:
                            # If _add is True and the standardized description already exists, raise an error
                            raise ValueError(f"Data for '{standardized_desc_name}' under '{classification_name}' already exists.")

                # If you want to add it than process the data as necessary
                if add_remove:
                    # Convert the descriptions to a list of dictionaries
                    desc_list = [{"name": desc} for desc in descriptions]
    
                    new_standardized_desc = {
                        "name": standardized_desc_name,
                        "web": data_list[-1],
                        "descriptions": desc_list
                    }
                    classification["standardized_descriptions"].append(new_standardized_desc)
                    print(f"Data for '{standardized_desc_name}' under '{classification_name}' added successfully.")
                    save_to_json(file_path)
                    return
                else:
                    # If you want to remove it than raise an error
                    raise ValueError(f"Data for '{standardized_desc_name}' under '{classification_name}' do not exists.")
    
    except ValueError as e:
        print(e)
        return

# # Example usage:
# update_json("data/datasetup.json", ["spesa", "TEST", ["PAOLO", "PAOLO"], True], False)

def check_regex_collisions(desc_series, file_path = 'data/datasetup.json'):
    '''
    Verifies if each value of the input series matches multiple regex patterns.

    Args:
        - desc_series (pd.Series): The series to search.
        - file_path (str): Path to the JSON file.
    '''

    try:
        assert os.path.exists(file_path), f"JSON file does not exist."
        assert isinstance(desc_series, pd.Series), f"Not a valid input Series"
    except AssertionError as e:
        print(e)
        return

    def regex_match(value, find_descr, replace_descr):
        """
        Replace descriptions in the value based on regex patterns.
        
        Args:
        - value (str): The input text value.
        - find_descr (list of str): List of descriptions to find.
        - replace_descr (list of str): List of descriptions to replace.
        
        Returns:
        - str: The updated text value after replacements.
        """
        
        # Create a list to store the modified values
        modified_values = []
        
        # Iterate over each description and its corresponding replacement
        for find, replace in zip(find_descr, replace_descr):
            # Generate the regex pattern
            pattern = re.compile('.*' + find + '.*')
            
            # Perform the regex search
            match = pattern.search(value)
            
            # If a match is found, replace the description
            if match:
                modified_values.append((replace, find, value)) # debug
        
        # If multiple matches are found, raise an error
        if len(modified_values) > 1:
            return(modified_values)

    try:
        # The datasetup_proxy from utils is used to update the srandard descriptions.
        _, _, replace_descr, find_descr = datasetup_proxy(file_path)
    
        # Print values in the original series for which multiple matches are found.
        for value in desc_series.values:
            result = regex_match(value, find_descr, replace_descr)
            if result:
                print(result)
    except Exception as e:
        print(e)
        return


from data import datasetup

def construct_json(find_descr, replace_descr, _web, _classifier, output_file_path):
    """
    Construct a JSON structure based on provided descriptions, standardized descriptions,
    and classifications. The resulting JSON structure is saved to a file.

    Args:
        find_descr (list): List of original descriptions.
        replace_descr (list): List of standardized descriptions corresponding to the original descriptions.
        _web (list): List of standardized descriptions where the 'web' attribute is True.
        _classifier (dict): Dictionary with classifications as keys and lists of matching standardized descriptions as values.
        output_file_path (str): Path to the output JSON file.

    Returns:
        dict: JSON data representing the constructed structure.
    """

    # Base JSON structure
    json_data = {
        "classifications": []
    }

    # Create a lookup dictionary for _web for quick lookups
    web_lookup = {_web_item: True for _web_item in _web}

    # Ensure lengths of find_descr and replace_descr match
    if len(find_descr) != len(replace_descr):
        raise ValueError("Lengths of find_descr and replace_descr must be equal.")

    # Process each classifier and standardized description
    for classifier, standardized_descriptions in _classifier.items():
        classifier_entry = {
            "name": classifier,
            "standardized_descriptions": []
        }
        
        for std_descr in standardized_descriptions:
            std_descr_entry = {
                "name": std_descr,
                "web": web_lookup.get(std_descr, False),
                "descriptions": []
            }

            # Add descriptions if they match the current standardized description
            for idx, descr in enumerate(find_descr):
                if replace_descr[idx] == std_descr:
                    descr_entry = {
                        "name": descr.strip('.*')
                    }
                    std_descr_entry["descriptions"].append(descr_entry)

            classifier_entry["standardized_descriptions"].append(std_descr_entry)

        json_data["classifications"].append(classifier_entry)

    # Save json_data to a JSON file
    with open(output_file_path, 'w') as outfile:
        json.dump(json_data, outfile, indent=4)

    print(f"Data saved to {output_file_path}")

    return json_data


# # Usage:

# from backup import datasetup_copia as datasetup

# find_descr_list = datasetup.find_descr  # List of original descriptions
# replace_descr_list = datasetup.replace_descr  # List of corresponding standardized_descriptions
# web_list = datasetup._web  # List of standardized_descriptions where web is True
# classifier_dict = datasetup._classifier  # Dictionary with classifications and lists of matching standardized_descriptions

# json_result = construct_json(find_descr_list, replace_descr_list, web_list, classifier_dict, 'data/datasetup.json')
# print(json.dumps(json_result, indent=4))







