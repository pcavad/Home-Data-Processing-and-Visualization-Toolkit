import json
import pandas as pd
from pathlib import Path
from pprint import pprint
import re, os
from pydantic import (BaseModel, 
    Field,
    PrivateAttr,
    ConfigDict,
    FilePath)
from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware
from typing import List, Dict, Optional, Any, Annotated, Literal

# Config
from .config import TINYDB_FILEPATH



############# POSSIBLE METHODS TO BE IMPLEMENTED #################


#   result = [f"{res}: {str(table.count(query.classification == res))}" for res in {row["classification"] for row in table.all()}]
#   sorted_result = sorted(result, key=lambda x: int(x.split(': ')[1]), reverse=True)
#   print("\n".join(sorted_result))

####################################################################

# 1. Define the Data Schema
class DescriptionRecord(BaseModel):
    name: str
    classification: str
    descriptions: List[str] = Field(default_factory=list)
    update_exception: bool = False
    web: bool = False
    essential: int = 0
    recurrent: int = 0
    product_service: int = 0
    
    # Allows Pydantic to work smoothly if you add custom methods
    # model_config = ConfigDict(from_attributes=True)


# 2. Utility class used in find_overlaps method
class OverlapMatch(BaseModel):
    term: str
    entity: str
    classification: str
    matches_with: str
    other_entity: str
    other_classification: str
    
    @property
    def summary(self) -> str:
        """A more readable description of the overlap."""
        return (f"Overlap Found: '{self.term}' (from {self.entity}) "
                f"is contained within '{self.matches_with}' (from {self.other_entity})")


class Store(BaseModel):
    ConfigDict(extra="forbid", strict=True)
    db_path: Annotated[FilePath, Field(validate_default=True)] = TINYDB_FILEPATH
    
    _db: TinyDB = PrivateAttr()
    _table: Any = PrivateAttr()
    _query: Query = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        self._db = TinyDB(self.db_path, storage=CachingMiddleware(JSONStorage))
        self._table = self._db.table("standardized_descriptions")
        self._query = Query()

    def __enter__(self): return self
    def __exit__(self, *args): self._db.close()

    # --- Retrieval Methods ---

    def get_all(self) -> List[DescriptionRecord]:
        """Returns all records, automatically validated into Pydantic objects."""
        return [DescriptionRecord(**item) for item in self._table.all()]

    def search_by_name(self, pattern: str, flag: Literal[re.RegexFlag.I] = re.IGNORECASE) -> List[DescriptionRecord]:
        """Finds records matching a pattern and returns validated objects."""
        regex = '.*' + re.escape(pattern) + '.*'
        results = self._table.search(self._query.name.matches(regex, flags=flag))
        return [DescriptionRecord(**item) for item in results]

    def get_by_update_exception(self, status: bool = True) -> List[DescriptionRecord]:
        results = self._table.search(self._query.update_exception == status)
        return [DescriptionRecord(**item) for item in results]

    # --- Write Methods ---

    def insert_document(self, doc: Dict[str, Any]) -> None:
        """Validates and checks for duplicates using Pydantic."""
        try:
            # Pydantic replaces manual 'require_validate_doc'
            record = DescriptionRecord(**doc)
            
            if self._table.search(self._query.name == record.name):
                print(f"Rolling back - duplicated name found: {record.name}")
                return

            self._table.insert(record.model_dump())
            print(f"Document '{record.name}' inserted successfully.")
        except Exception as e:
            print(f"Validation/Insertion Error: {e}")

    def update_by_name(self, name: str, updates: Dict[str, Any]):
        # We use model_dump(exclude_unset=True) if you want to validate partial updates
        self._table.update(updates, self._query.name == name)

    def add_description(self, name: str, new_description: str):
        """Appends a string to the 'descriptions' list."""
        def transform(doc):
            doc.setdefault("descriptions", []).append(new_description)
        self._table.update(transform, self._query.name == name)

    def remove_description(self, name: str, one_description: str):
        """Appends a string to the 'descriptions' list."""
        def transform(doc):
            doc.setdefault("descriptions", []).remove(one_description)
        self._table.update(transform, self._query.name == name)

    def rename_entry(self, old_name: str, new_name: str):
        """Renames a record's 'name' field."""
        # Simple update using the private query and table
        self._table.update({"name": new_name}, self._query.name == old_name)

    def remove_by_name(self, name: str):
        """Removes a record matching the exact name."""
        self._table.remove(self._query.name == name)

    def clear_exceptions_except(self, exclusion_name: str = "cartimpronta"):
        """
        Removes records where update_exception is True, 
        unless the name matches the exclusion.
        """
        # Logic remains the same, leveraging the TinyDB Query operators
        condition = (self._query.name != exclusion_name) & (self._query.update_exception == True)
        self._table.remove(condition)

    # --- Utility Methods ---

    def find_overlaps(self) -> List[OverlapMatch]:
        """Analyzes overlaps and returns a list of OverlapMatch objects."""
        records = self.get_all()  # Returns List[DescriptionRecord]
        all_terms = []

        # 1. Flatten descriptions using object attributes
        for rec in records:
            for term in rec.descriptions:
                if term:
                    all_terms.append({
                        "classification": rec.classification,
                        "entity": rec.name,
                        "term": term.strip()
                    })

        matches = []
        # 2. Compare terms
        for i, item in enumerate(all_terms):
            # Regex for word boundary matching
            pattern = re.compile(rf"(^|\W){re.escape(item['term'])}(\W|$)")
            
            for j, other in enumerate(all_terms):
                if i == j:
                    continue
                
                if pattern.search(other["term"]):
                    # Create a Pydantic OverlapMatch object
                    match_obj = OverlapMatch(
                        term=item["term"],
                        entity=item["entity"],
                        classification=item["classification"],
                        matches_with=other["term"],
                        other_entity=other["entity"],
                        other_classification=other["classification"]
                    )
                    matches.append(match_obj)
        
        return matches


    def get_classification_counts(self) -> List[str]:
        """Get the number of items for each classification."""
        all_docs = self.get_all()
        classifications = {rec.classification for rec in all_docs}
        
        counts = [
            f"{cls}: {self._table.count(self._query.classification == cls)}" 
            for cls in classifications
        ]
        return sorted(counts, key=lambda x: int(x.split(': ')[1]), reverse=True)

    # --- Used by data_manager.load_data() ---

    def get_metadata_tinydb(self) -> tuple:
        """
        Used to fetch metadata to load_data and update the standardized descriptions.
        """
        records = self.get_all()

        # Data containers
        classifier_dict = {}
        std_list, desc_list, web_list, update_list = [], [], [], []
        ess_list, rec_list, ps_list = [], [], []

        for rec in records:
            # Mapping
            classifier_dict.setdefault(rec.classification, []).append(rec.name)

            # Attribute Tuples
            ess_list.append((rec.name, rec.essential))
            rec_list.append((rec.name, rec.recurrent))
            ps_list.append((rec.name, rec.product_service))

            # Flags
            if rec.web: web_list.append(rec.name)
            if rec.update_exception: update_list.append(rec.name)

            # Flattening
            for d in rec.descriptions:
                desc_list.append(d)
                std_list.append(rec.name)

        return (classifier_dict, std_list, desc_list, web_list, 
                ess_list, rec_list, ps_list, update_list)