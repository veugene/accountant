import csv
from database import Transaction


def parse_csv(csv_file_io):
    transaction_list = []
    reader = csv.reader(csv_file_io)
    for line in reader:
        transaction = parse_line(line)
        if transaction is not None:
            transaction_list.append(transaction)
    return transaction_list


def parse_line(csv_line):
    assert isinstance(csv_line, list)
    if len(csv_line) == 4:
        # CIBC
        return Transaction(
            date=csv_line[0],
            name=csv_line[1],
            amount=string_to_float(csv_line[2]) + string_to_float(csv_line[3]),
        )
    if len(csv_line) == 12:
        # Rogers Mastercard
        return Transaction(
            date=csv_line[0],
            name=csv_line[6],
            amount=string_to_float(csv_line[11]),
        )
    if len(csv_line) == 5:
        # Rogers Mastercard from spreadsheet
        return Transaction(
            date=csv_line[0],
            name=csv_line[2],
            amount=string_to_float(csv_line[4]),
        )
    return None
        

def string_to_float(string):
    if string == '':
        return 0.
    return float(string.strip('$'))