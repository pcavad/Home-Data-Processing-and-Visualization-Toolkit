import json
from backup import datasetup_copia as datasetup

import json, re

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
                        "name": descr
                    }
                    std_descr_entry["descriptions"].append(descr_entry)

            classifier_entry["standardized_descriptions"].append(std_descr_entry)

        json_data["classifications"].append(classifier_entry)

    # Save json_data to a JSON file
    with open(output_file_path, 'w') as outfile:
        json.dump(json_data, outfile, indent=4)

    print(f"Data saved to {output_file_path}")

    return json_data


# Usage:
find_descr_list = datasetup.find_descr  # List of original descriptions
replace_descr_list = datasetup.replace_descr  # List of corresponding standardized_descriptions
web_list = datasetup._web  # List of standardized_descriptions where web is True
classifier_dict = datasetup._classifier  # Dictionary with classifications and lists of matching standardized_descriptions

# json_result = construct_json(find_descr_list, replace_descr_list, web_list, classifier_dict, 'data/datasetup.json')
# print(json.dumps(json_result, indent=4))


def update_json(file_path, data_list, _add):
    """
    Update a JSON object by adding or removing data based on the provided list.

    Args:
    - file_path (str): Path to the JSON file.
    - data_list (list): List of data to add or remove.
                        Example: ["Classification_Name", "Standardized_Desc_name", ("Desc_1", "Desc_2", ...), True/False]
    - _add (bool): True to add the data, False to remove the data.
    
    Raises:
    - ValueError: If the data_list already exists when trying to add or doesn't exist when trying to remove.
    """

    try:
        # Load the existing JSON data from the file
        with open(file_path, 'r') as file:
            json_data = json.load(file)
    
        classification_name = data_list[0]
        standardized_desc_name = data_list[1]
        descriptions = list(data_list[2])

        # Check if data_list doesn't exist if _add is False
        if all(classification_name not in classification['name'] for classification in json_data['classifications']):
            raise ValueError(f"No existing classification '{classification_name}' found to add data.")
    
        # Search for the classification in the JSON data
        for classification in json_data["classifications"]:
            if classification["name"] == classification_name:
                # Check if the standardized description name exists under the classification
                for standardized_desc in classification["standardized_descriptions"]:
                    if standardized_desc["name"] == standardized_desc_name:
                        if not _add:
                            # Remove the data from the JSON object
                            classification["standardized_descriptions"].remove(standardized_desc)
                            print(f"Data for '{standardized_desc_name}' under '{classification_name}' removed successfully.")
                            break
                        else:
                            # If _add is True and the standardized description already exists, raise an error
                            raise ValueError(f"Data for '{standardized_desc_name}' under '{classification_name}' already exists.")
                
                if _add:
                    # Convert the descriptions to a list of dictionaries
                    desc_list = [{"name": desc} for desc in descriptions]
    
                    new_standardized_desc = {
                        "name": standardized_desc_name,
                        "web": data_list[-1],
                        "descriptions": desc_list
                    }
                    classification["standardized_descriptions"].append(new_standardized_desc)
                    print(f"Data for '{standardized_desc_name}' under '{classification_name}' added successfully.")
                    break
    
        # Save the updated JSON data back to the file
        with open(file_path, 'w') as file:
            json.dump(json_data, file, indent=4)
    
        print(f"Updated JSON data saved to '{file_path}'.")
    except ValueError as e:
        print(e)

# Example usage:

# update_json("data/datasetup.json", ["spesa", "SPESA TEST", (".*PAOLO.*", ".*PAOLO.*"), False], False)






