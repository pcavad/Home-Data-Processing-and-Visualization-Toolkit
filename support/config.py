from pathlib import Path

DATA_PATH = "data"
SQLDB_FILEPATH = "data/transazioni.db"
CSV_FILEPATH = "data/transazioni.csv"
TINYDB_FILEPATH = "data/metadata_tinydb.json"
JSON_DATA_DICT_FILEPATH = "data/data_dict.json"
CREDIT_CARD_FOLDERS = ["paolo", "gunda"]
BANK_ACCOUNT_FOLDER = ["conto"]
PERSONAL_FILES = ['spesa individuale', 'spesa condivisa']
TITOLARI = ['paolo', 'gunda']

COLUMNS=['data_operazione', 'data_registrazione', 'descrizione', 'importo',
    'file', 'titolare', 'descrizione_standardizzata', 'classificazione', 'canale']

CLASSIFICATIONS = ['spesa', 'shopping', 'ristoranti', 'asporto', 'viaggi',
                    'salute', 'esperienze', 'abbonamenti', 'auto', 'casa', 'utenze']

CLASS_FILTERS_DICT = {
    "per_vivere": ['spesa', 'shopping', 'ristoranti', 'asporto', 'viaggi',
                    'salute', 'esperienze', 'abbonamenti'],
    "per_auto": ['auto'],
    "per_casa": ['casa'],
    "utenze": ['utenze']
}

DATE_FMT = "%Y-%m-%d"